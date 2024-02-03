# -*- coding: utf-8 -*-
from odoo import fields, models, api


class AppointmentType(models.Model):
    _inherit = "appointment.type"

    fsm_task_create = fields.Boolean(string="Create FSM Task",
                                     help="For each scheduled appointment, create a fsm task and assign it to the responsible user.")
    project_id = fields.Many2one('project.project', string="Project")
    task_count = fields.Integer(string='# Tasks', compute='_compute_task_count')

    def action_view_fsm_tasks(self):
        task_ids = self.meeting_ids.fsm_task_id.ids
        return {
            'name': 'Tasks',
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'target': 'current',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', task_ids), ('is_fsm', '=', True)],
        }

    @api.depends('meeting_ids')
    def _compute_task_count(self):
        for appointment_type in self:
            appointment_type.task_count = len(appointment_type.meeting_ids.fsm_task_id)
