# -*- coding: utf-8 -*-

from odoo import fields, models


class VoipCall(models.Model):
    _inherit = "voip.call"

    log_id = fields.Char(string="Log ID")
