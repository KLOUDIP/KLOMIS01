# -*- coding: utf-8 -*-
from odoo import models, fields


class FiosDevice(models.Model):
    _name = 'fios.device'
    _description = 'FIOS Device'
    _order = 'name'

    partner_id = fields.Many2one('res.partner', string='Customer', required=True,
                                 ondelete='cascade', index=True)
    name = fields.Char(string='Device / Plate')
    imei = fields.Char(string='IMEI')
    phone = fields.Char(string='Phone')
    active = fields.Boolean(string='Activated')