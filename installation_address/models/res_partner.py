# -*- coding: utf-8 -*-
from odoo import fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'

    type = fields.Selection(selection_add=[("installation", "Installation Address")])

