from datetime import datetime, time
from odoo.addons.timesheet_grid.wizard.project_task_create_timesheet import ProjectTaskCreateTimesheet
from odoo import api, fields, models, _


def save_timesheet(self):
    values = {
        'task_id': self.task_id.id,
        'project_id': self.task_id.project_id.id,
        'date': fields.Date.context_today(self),
        'name': self.description,
        'user_id': self.env.uid,
        'unit_amount': self.time_spent,
        'start_time': self.start_time,
        'end_time': datetime.now()
    }
    self.task_id.user_timer_id.unlink()
    return self.env['account.analytic.line'].create(values)


ProjectTaskCreateTimesheet.save_timesheet = save_timesheet


class ProjectTaskCreateTimesheet(models.TransientModel):
    _inherit = 'project.task.create.timesheet'

    start_time = fields.Datetime(string="Start Time", related='task_id.real_start_time')
    end_time = fields.Datetime(string="End Time", default=datetime.now())