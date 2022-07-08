from odoo import api, fields, models, _
from datetime import datetime, time

class HrTimesheet(models.Model):
    _inherit = 'account.analytic.line'

    start_time = fields.Datetime(string="Start Time")
    end_time = fields.Datetime(string="End Time")




