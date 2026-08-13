# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _


class MissingSerial(models.Model):
    _name = 'missing.serial'
    _description = 'Missing Serial'
    _rec_name = 'unit_serial'

    partner_id = fields.Many2one('res.partner', 'Partner')
    unit_serial = fields.Char(string='Serial Number')
    state = fields.Selection([
        ('not_updated', 'Waiting for Matching'),
        ('updated', 'Matched'),
    ], string='State', default='not_updated')