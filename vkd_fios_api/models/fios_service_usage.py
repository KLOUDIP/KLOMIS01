# -*- coding: utf-8 -*-
from odoo import models, fields


class FiosServiceUsage(models.Model):
    _name = 'fios.service.usage'
    _description = 'FIOS Service Usage'
    _order = 'name'

    partner_id = fields.Many2one('res.partner', string='Customer', required=True,
                                 ondelete='cascade', index=True)
    name = fields.Char(string='Service')
    service_code = fields.Char(string='FIOS Service')
    usage = fields.Integer(string='Used')
    limit = fields.Char(string='Limit')
    feature = fields.Boolean(string='Feature Service')
    enabled = fields.Boolean(string='Enabled')