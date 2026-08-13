from odoo import api, fields, models, _
from datetime import datetime, time

class Task(models.Model):
    _inherit = 'project.task'

    real_start_time = fields.Datetime(string="Start Time")
    partner_email = fields.Char(string="Email", track_visibility='onchange')

    def action_timer_start(self):
        res = super(Task, self).action_timer_start()
        self.real_start_time = datetime.now()
        return res