# -*- coding: utf-8 -*-
from odoo import fields, models


class Task(models.Model):
    _inherit = "project.task"

    is_appointment = fields.Boolean(string="FSM Appointment", compute="_check_appointment")

    def _check_appointment(self):
        appointment = self.env['calendar.event']
        for record in self:
            record.is_appointment = bool(appointment.search([('fsm_task_id', '=', record.id)]).id)

    def action_view_appointment(self):
        appointment = self.env['calendar.event'].search([('fsm_task_id', '=', self.id)])
        return {
            'name': 'Online Appointments',
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            'target': 'current',
            'res_id': appointment.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
        }
