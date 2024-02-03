# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CalendarEventFsm(models.Model):
    _inherit = 'calendar.event'

    fsm_task_id = fields.Many2one("project.task", string="FSM Task")

    @api.model_create_multi
    def create(self, vals_list):
        events = super().create(vals_list)
        events.filtered(lambda e: e.appointment_type_id.fsm_task_create).sudo()._create_fsm_task_from_appointment()
        return events

    def _create_fsm_task_from_appointment(self):
        task_values = []
        for event in self:
            partner = event.partner_ids
            task_values.append(event._get_fsm_task_values(partner[:1]))

        # Create tasks within the event organizer's company
        tasks = self.env['project.task'].with_context(mail_create_nosubscribe=True) \
            .with_company(self.user_id.company_id).create(task_values)
        for event, task in zip(self, tasks):
            event._link_with_fsm_task(task)
        return tasks

    def _get_fsm_task_values(self, partner):
        return {
            'name': self.name,
            'partner_id': partner.id,
            'project_id': self.appointment_type_id.project_id.id,
            'planned_date_begin': self.start,
            'planned_date_end': self.stop,
            'date_deadline': self.stop_date,
            'is_fsm': True,
            'description': self.description,
        }

    def _link_with_fsm_task(self, task):
        self.write({
            'res_model_id': self.env['ir.model']._get(task._name).id,
            'res_id': task.id,
            'fsm_task_id': task.id,
        })