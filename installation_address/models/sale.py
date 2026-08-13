# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    partner_installation_id = fields.Many2one(
        'res.partner',
        string='Installation Address',
        compute='_compute_partner_installation_id',
        store=True,
        readonly=False,
        precompute=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]"
    )

    @api.depends('partner_id')
    def _compute_partner_installation_id(self):
        for order in self:
            if order.partner_id:
                addr = order.partner_id.address_get(['installation'])
                order.partner_installation_id = addr.get('installation')
            else:
                order.partner_installation_id = False
