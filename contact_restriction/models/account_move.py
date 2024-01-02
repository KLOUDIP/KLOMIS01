# -*- coding: utf-8 -*-

from odoo import models, api
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def create(self, values):
        partner = self.env['res.partner'].browse(values.get('partner_id'))
        invoice_partner = self.env['res.partner'].browse(values.get('partner_invoice_id'))
        if partner and partner.is_blocked or invoice_partner.is_blocked:
            raise UserError("This contact is blocked. You cannot create a Sales Order.")
        return super(AccountMove, self).create(values)

    def write(self, values):
        rec = super(AccountMove, self).write(values)
        if self.partner_id.is_blocked or self.partner_invoice_id.is_blocked:
            raise UserError("This contact is blocked.")
        return rec
