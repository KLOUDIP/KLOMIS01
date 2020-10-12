# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class TaskCustomReport(models.AbstractModel):
    _name = 'report.field_service_worksheet_template.custom_worksheet'
    _description = 'Task Worksheet Custom Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['worksheet.template.line'].browse(docids).sudo()

        worksheet_map = {}
        for task in docs.project_task_id:
            if task.worksheet_template_id:
                task._reflect_timesheet_quantities()
        x_model = docs.template_id.model_id.model
        worksheet = self.env[x_model].search([('x_studio_line_id', '=', docs.id)], limit=1, order="create_date DESC")
        worksheet_map[docs.id] = worksheet

        return {
            'doc_ids': docids,
            'doc_model': 'worksheet.template.line',
            'docs': docs,
            'worksheet_map': worksheet_map,
        }
