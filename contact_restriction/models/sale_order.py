# -*- coding: utf-8 -*-

from odoo import models, api
from odoo.exceptions import UserError

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def create(self, values):
        partner = self.env['res.partner'].browse(values.get('partner_id'))
        invoice_partner = self.env['res.partner'].browse(values.get('partner_invoice_id'))
        if partner and partner.is_blocked or invoice_partner.is_blocked:
            raise UserError("This contact is blocked. You cannot create a Sales Order.")
        return super(SaleOrder, self).create(values)

    def write(self, values):
        rec = super(SaleOrder, self).write(values)
        if self.partner_id.is_blocked or self.partner_invoice_id.is_blocked:
            raise UserError("This contact is blocked.")
        return rec
