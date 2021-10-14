# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    coordination_by_id = fields.Many2one('res.partner', string='Coordination By')
    billing_by_id = fields.Many2one('res.partner', string='Billing By')
