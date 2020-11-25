# -*- coding: utf-8 -*-
from odoo import api, fields, models, SUPERUSER_ID, _

class SaleOrder(models.Model):
    _inherit = "sale.order"

    partner_installation_id = fields.Many2one('res.partner', string='Installation Address', readonly=True, required=True,
        states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'sale': [('readonly', False)]},
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",)

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        super(SaleOrder, self).onchange_partner_id()
        addr = self.partner_id.address_get(['installation'])
        values = {'partner_installation_id': addr['installation']}
        self.update(values)

