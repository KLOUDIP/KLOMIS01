# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    expense_id_worksheet_line = fields.Many2one('worksheet.template.line', 'Worksheet Id')
    worksheet_task_id = fields.Many2one('project.task', 'Task Id')

    @api.model
    def create(self, vals):
        res = super(AccountMove, self).create(vals)
        if res.expense_id_worksheet_line:
            res.expense_id_worksheet_line.write({'other_3': True})
        return res

    def action_view_project_task(self):
        if self.worksheet_task_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'project.task',
                'view_mode': 'form',
                'res_id': self.worksheet_task_id.id,
            }
