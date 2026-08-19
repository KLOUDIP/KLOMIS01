# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only.
from odoo import fields, models


class Website(models.Model):
    _inherit = "website"

    google_tag = fields.Char(string='Google Tag', size=255)
