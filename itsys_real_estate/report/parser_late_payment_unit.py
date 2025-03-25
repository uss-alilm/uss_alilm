# -*- coding: utf-8 -*-
import time
from datetime import datetime, date,timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class Parser(models.AbstractModel):
    _name = 'report.itsys_real_estate.report_late_payments_units'

    def _get_lines(self,start_date, end_date, unit_ids):
        now = datetime.today().date()
        domain = [('date','>=',start_date),('date','<=',end_date),('date','<',now),('amount_residual','>',0)]
        if unit_ids: domain.append(('contract_partner_id','in',self.partner_ids.ids))
        loans=self.env['loan.line.rs.own'].search(domain)
        return loans

    def _get_total(self,start_date, end_date, unit_ids):
        now = datetime.today().date()
        domain = [('date','>=',start_date),('date','<=',end_date),('date','<',now),('amount_residual','>',0)]
        if unit_ids: domain.append(('contract_partner_id','in',self.partner_ids.ids))
        loans=self.env['loan.line.rs.own'].search(domain)
        sum=0.0
        for line in loans:
            sum+=line.amount_residual
        return sum

    @api.model
    def _get_report_values(self, docids, data=None):
        if not data.get('form'):
            raise UserError(_("Form content is missing, this report cannot be printed."))

        due_payment = self.env['ir.actions.report']._get_report_from_name('itsys_real_estate.report_late_payments_units')

        return {
            'doc_ids': self.ids,
            'doc_model': due_payment.model,
            'date_start':data['form']['date_start'],
            'date_end':data['form']['date_end'],
            'get_lines': self._get_lines(data['form']['date_start'],data['form']['date_end'],data['form']['building_unit']),
            'get_total': self._get_total(data['form']['date_start'],data['form']['date_end'],data['form']['building_unit']),
        }