from odoo import api, fields, models, _
from datetime import datetime, time

class ProjectTaskCreateTimesheet(models.TransientModel):
    _inherit = 'project.task.create.timesheet'

    start_time = fields.Datetime(string="Start Time", related='task_id.real_start_time')
    end_time = fields.Datetime(string="End Time", default=datetime.now())

    def save_timesheet(self):
        res = super(ProjectTaskCreateTimesheet, self).save_timesheet()
        res.update({
            'start_time': self.start_time,
            'end_time': datetime.now(),
        })
        return res
