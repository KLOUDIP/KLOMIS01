# -*- encoding: utf-8 -*-
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    billing_by_id = fields.Many2one(
        'hr.employee',
        string='Billing By',
        compute='_compute_billing_responsible',
        store=True,
        readonly=False,
        precompute=True
    )

    @api.depends('partner_id', 'partner_id.billing_by_id', 'partner_id.parent_id.coordination_by_id',
                 'partner_id.parent_id.billing_by_id')
    def _compute_billing_responsible(self):
        """ Get billing by to current invoice """
        for rec in self:
            if rec.partner_id:
                if rec.partner_id.parent_id:
                    rec.billing_by_id = rec.partner_id.parent_id.billing_by_id.id
                else:
                    rec.billing_by_id = rec.partner_id.billing_by_id.id
            else:
                rec.billing_by_id = False
