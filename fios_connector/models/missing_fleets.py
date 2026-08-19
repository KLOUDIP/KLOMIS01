# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only.
from odoo import fields, models


class MissingFleets(models.Model):
    _name = 'missing.fleets'
    _description = 'Missing Fleets'
    _rec_name = 'plate_no'

    partner_id = fields.Many2one('res.partner', 'Partner')
    plate_no = fields.Char(string='Plate Number')
    item_id = fields.Char(string='Item ID')
    state = fields.Selection([
        ('not_updated', 'Waiting for Matching'),
        ('updated', 'Matched'),
    ], string='State', default='not_updated')
