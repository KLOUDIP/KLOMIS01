# -*- coding: utf-8 -*-
from odoo import fields, models


class AppointmentType(models.Model):
    _inherit = "appointment.type"

    fsm_task_create = fields.Boolean(string="Create FSM Task",
        help="For each scheduled appointment, create a fsm task and assign it to the responsible user.")
    project_id = fields.Many2one('project.project', string="Project")
