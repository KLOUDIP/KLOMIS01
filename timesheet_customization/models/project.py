# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only.
from odoo import fields, models


class Task(models.Model):
    _inherit = 'project.task'

    real_start_time = fields.Datetime(string="Start Time")
    # v17 passed track_visibility='onchange', removed from the ORM in v13 and
    # silently ignored ever since. Dropped rather than converted to
    # tracking=True, which would start writing messages that never existed.
    partner_email = fields.Char(string="Email")

    # NOTE: the action_timer_start() override is dropped along with the
    # timesheet_grid dependency.
