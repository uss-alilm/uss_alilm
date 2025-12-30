# -*- coding: utf-8 -*-
import base64
import pytz
import binascii

from odoo import api, fields, models
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


def _tlv(tag, value):
    value = value or ""
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

    # ✅ TLV Base64 string used by /report/barcode QR
    qr_str = fields.Char(string="ZATCA QR (TLV Base64)", compute="_compute_qr_str", store=False)

    # ✅ optional booleans (if your views use them)
    qr_button = fields.Boolean(string="Qr Button", compute="_compute_qr_flags", store=False)
    qr_page = fields.Boolean(string="Qr Page", compute="_compute_qr_flags", store=False)

    einv_amount_sale_total = fields.Monetary(string="Amount sale total", compute="_compute_total", store=True)
    einv_amount_discount_total = fields.Monetary(string="Amount discount total", compute="_compute_total", store=True)
    einv_amount_tax_total = fields.Monetary(string="Amount tax total", compute="_compute_total", store=True)

    @api.depends("invoice_line_ids", "amount_total", "amount_untaxed")
    def _compute_total(self):
        for r in self:
            r.einv_amount_sale_total = r.amount_untaxed + sum(line.einv_amount_discount for line in r.invoice_line_ids)
            r.einv_amount_discount_total = sum(line.einv_amount_discount for line in r.invoice_line_ids)
            r.einv_amount_tax_total = sum(line.einv_amount_tax for line in r.invoice_line_ids)

    @api.depends("company_id.country_id.code", "move_type", "partner_id.vat")
    def _compute_qr_flags(self):
        """
        Logic you want for showing QR button/page.
        Adjust as you like.
        """
        for m in self:
            is_sa = (m.company_id.country_id.code == "SA")
            m.qr_button = is_sa
            m.qr_page = is_sa

    @api.depends("company_id.name", "company_id.vat", "invoice_date", "create_date", "amount_total", "amount_tax")
    def _compute_qr_str(self):
        for m in self:
            # only Saudi (optional)
            if m.company_id.country_id.code != "SA":
                m.qr_str = False
                continue

            seller = m.company_id.name or ""
            vat = m.company_id.vat or ""

            # Timestamp (ISO)
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
            m.qr_str = base64.b64encode(tlv).decode("utf-8")

    # ✅ keep this helper if you want to call it from QWeb
    def _get_qr_code(self):
        self.ensure_one()
        return self.qr_str or ""
    def generate_qr_button(self):
        # لم نعد نحتاج توليد يدوي
        # لكن نتركها حتى لا يكسر الـ View
        return True
        
    qr = fields.Binary(string="QR Code", help="(Deprecated) Kept for compatibility with views.")

