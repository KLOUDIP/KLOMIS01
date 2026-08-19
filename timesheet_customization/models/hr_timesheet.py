# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only.
from odoo import fields, models


class HrTimesheet(models.Model):
    _inherit = 'account.analytic.line'

    start_time = fields.Datetime(string="Start Time")
    end_time = fields.Datetime(string="End Time")
