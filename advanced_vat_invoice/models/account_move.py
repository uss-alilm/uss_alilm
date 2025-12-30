# -*- coding: utf-8 -*-
from io import BytesIO
import binascii
import base64
import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

try:
    import qrcode
except ImportError:
    qrcode = None


def _tlv(tag, value):
    if value is None:
        value = ""
    if not isinstance(value, str):
        value = str(value)
    b = value.encode("utf-8")
    return bytes([tag, len(b)]) + b


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    einv_amount_discount = fields.Monetary(
        string="Amount discount",
        compute="_compute_amount_discount",
        store=True,
    )
    einv_amount_tax = fields.Monetary(
        string="Amount tax",
        compute="_compute_amount_tax",
        store=True,
    )

    @api.depends("discount", "quantity", "price_unit")
    def _compute_amount_discount(self):
        for r in self:
            r.einv_amount_discount = r.quantity * r.price_unit * (r.discount / 100.0)

    @api.depends("tax_ids", "discount", "quantity", "price_unit", "price_subtotal")
    def _compute_amount_tax(self):
        for r in self:
            r.einv_amount_tax = sum(r.price_subtotal * (tax.amount / 100.0) for tax in r.tax_ids)


class AccountMove(models.Model):
    _inherit = "account.move"

    qr = fields.Binary(string="QR Code", compute="generate_qrcode", store=True, help="QR code")
    qr_button = fields.Boolean(string="Qr Button", compute="_compute_qr")
    qr_page = fields.Boolean(string="Qr Page", compute="_compute_qr")

    einv_amount_sale_total = fields.Monetary(string="Amount sale total", compute="_compute_total", store=True)
    einv_amount_discount_total = fields.Monetary(string="Amount discount total", compute="_compute_total", store=True)
    einv_amount_tax_total = fields.Monetary(string="Amount tax total", compute="_compute_total", store=True)

    x_zatca_qr_str = fields.Char(compute="_compute_zatca_qr_str", store=False)

    @api.depends("invoice_line_ids", "amount_total", "amount_untaxed")
    def _compute_total(self):
        for r in self:
            r.einv_amount_sale_total = r.amount_untaxed + sum(line.einv_amount_discount for line in r.invoice_line_ids)
            r.einv_amount_discount_total = sum(line.einv_amount_discount for line in r.invoice_line_ids)
            r.einv_amount_tax_total = sum(line.einv_amount_tax for line in r.invoice_line_ids)

    def timezone(self, userdate):
        tz_name = self.env.context.get("tz") or self.env.user.tz or "UTC"
        contex_tz = pytz.timezone(tz_name)
        date_time = pytz.utc.localize(userdate).astimezone(contex_tz)
        return date_time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

    def string_hexa(self, value):
        if value:
            string_bytes = str(value).encode("UTF-8")
            return binascii.hexlify(string_bytes).decode("UTF-8")
        return ""

    def hexa(self, tag, length, value):
        if tag and length and value:
            hex_string = self.string_hexa(value)
            length = int(len(hex_string) / 2)
            conversion_table = list("0123456789abcdef")
            hexadecimal = ""
            while length > 0:
                remainder = length % 16
                hexadecimal = conversion_table[remainder] + hexadecimal
                length = length // 16
            if len(hexadecimal) == 1:
                hexadecimal = "0" + hexadecimal
            return tag + hexadecimal + hex_string
        return ""

    def qr_code_data(self):
        """Generate TLV Base64 (ZATCA) using the original hexa method."""
        self.ensure_one()

        seller_name = str(self.company_id.name or "")
        seller_vat_no = self.company_id.vat or ""

        seller_hex = self.hexa("01", "0c", seller_name) or ""
        vat_hex = self.hexa("02", "0f", seller_vat_no) or ""

        time_stamp = (self.invoice_date and str(self.invoice_date) + "T00:00:00Z") or ""
        date_hex = self.hexa("03", "14", time_stamp) or ""

        # Convert to SAR (if you really need SAR), otherwise keep company currency
        sar = self.env.ref("base.SAR", raise_if_not_found=False)
        if sar:
            amount_total = self.currency_id._convert(
                self.amount_total, sar, self.env.company, self.invoice_date or fields.Date.today()
            )
            amount_tax = self.currency_id._convert(
                self.amount_tax, sar, self.env.company, self.invoice_date or fields.Date.today()
            )
        else:
            amount_total = self.amount_total
            amount_tax = self.amount_tax

        total_with_vat_hex = self.hexa("04", "0a", str(round(amount_total, 2))) or ""
        total_vat_hex = self.hexa("05", "09", str(round(amount_tax, 2))) or ""

        qr_hex = seller_hex + vat_hex + date_hex + total_with_vat_hex + total_vat_hex
        return base64.b64encode(bytes.fromhex(qr_hex)).decode()

    @api.depends("company_id.name", "company_id.vat", "invoice_date", "create_date", "amount_total", "amount_tax")
    def _compute_zatca_qr_str(self):
        for m in self:
            seller = m.company_id.name or ""
            vat = m.company_id.vat or ""

            if m.invoice_date:
                dt = str(m.invoice_date) + "T00:00:00Z"
            else:
                dt = (m.create_date or fields.Datetime.now()).strftime("%Y-%m-%dT%H:%M:%SZ")

            total = "%.2f" % (m.amount_total or 0.0)
            tax = "%.2f" % (m.amount_tax or 0.0)

            tlv = b"".join([
                _tlv(1, seller),
                _tlv(2, vat),
                _tlv(3, dt),
                _tlv(4, total),
                _tlv(5, tax),
            ])
            m.x_zatca_qr_str = base64.b64encode(tlv).decode("utf-8")

    def _get_qr_code(self):
        """Return TLV Base64 used by /report/barcode QR (works with your QWeb)."""
        self.ensure_one()
        return self.x_zatca_qr_str or self.qr_code_data() or ""

    @api.depends("state")
    def generate_qrcode(self):
        """Generate and save QR PNG after the invoice is posted (requires python qrcode lib)."""
        param = self.env["ir.config_parameter"].sudo()
        qr_code = param.get_param("advanced_vat_invoice.generate_qr")

        for rec in self:
            if rec.state != "posted":
                rec.qr = False
                continue

            if qr_code != "automatically":
                continue

            if not qrcode:
                # On Odoo.sh qrcode may not exist; don't crash invoice printing
                rec.qr = False
                continue

            qr = qrcode.QRCode(
                version=4,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=4,
                border=1,
            )
            qr.add_data(rec._get_qr_code())
            qr.make(fit=True)
            img = qr.make_image()
            temp = BytesIO()
            img.save(temp, format="PNG")
            rec.qr = base64.b64encode(temp.getvalue())

    def generate_qr_button(self):
        """Manually generate and save QR PNG."""
        param = self.env["ir.config_parameter"].sudo()
        qr_code = param.get_param("advanced_vat_invoice.generate_qr")

        for rec in self:
            if qr_code != "manually":
                continue

            if not qrcode:
                raise UserError(_("Python library 'qrcode' is not installed on this server."))

            qr = qrcode.QRCode(
                version=4,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=4,
                border=1,
            )
            qr.add_data(rec._get_qr_code())
            qr.make(fit=True)
            img = qr.make_image()
            temp = BytesIO()
            img.save(temp, format="PNG")
            rec.qr = base64.b64encode(temp.getvalue())
