# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    billing_by_id = fields.Many2one('res.partner', string='Billing By',
                                    compute='_compute_billing_responsible', store=True)

    @api.depends('partner_id', 'partner_id.coordination_by_id', 'partner_id.billing_by_id')
    def _compute_billing_responsible(self):
        """
        Get billing by to current invoice
        """
        for rec in self:
            if rec.partner_id.parent_id:
                billing = rec.partner_id.parent_id.billing_by_id.id
            else:
                billing = rec.partner_id.billing_by_id.id
            rec.update({
                'billing_by_id': billing,
            })
