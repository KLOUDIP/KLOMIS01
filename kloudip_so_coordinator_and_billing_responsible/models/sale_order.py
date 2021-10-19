# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    coordination_by_id = fields.Many2one('hr.employee', string='Coordination By',
                                         compute='_compute_coordination_and_billing_responsible', store=True)
    billing_by_id = fields.Many2one('hr.employee', string='Billing By',
                                    compute='_compute_coordination_and_billing_responsible', store=True)

    @api.depends('partner_id', 'partner_id.coordination_by_id', 'partner_id.billing_by_id', 'partner_id.parent_id.coordination_by_id', 'partner_id.parent_id.billing_by_id')
    def _compute_coordination_and_billing_responsible(self):
        """
        Get coordination and billing to current sale order
        """
        for rec in self:
            if rec.partner_id.parent_id:
                coordination = rec.partner_id.parent_id.coordination_by_id.id
                billing = rec.partner_id.parent_id.billing_by_id.id
            else:
                coordination = rec.partner_id.coordination_by_id.id
                billing = rec.partner_id.billing_by_id.id
            rec.update({
                'coordination_by_id': coordination,
                'billing_by_id': billing,
            })

