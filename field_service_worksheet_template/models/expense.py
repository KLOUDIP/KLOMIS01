from odoo import models, fields, api, _


class Expenses(models.Model):
    _inherit = 'hr.expense'

    expense_id_worksheet_line = fields.Many2one('worksheet.template.line', 'Worksheet Id')
    task_id_rec = fields.Many2one('project.task', 'Task Id')

    @api.model
    def create(self, vals):
        res = super(Expenses, self).create(vals)
        line_id = self.env.context.get('active_id')
        task_line_id = self.env['worksheet.template.line'].search([('id', '=', line_id)])
        get_context = self._context['product_val']
        if get_context == 'food':
            task_line_id.write({
                'food': True,
            })
        if get_context == 'beverage':
            task_line_id.write({
                'beverage': True,
            })
        if get_context == 'transport':
            task_line_id.write({
                'transport': True,
            })

        if get_context == 'extra':
            task_line_id.write({
                'extra': True,
            })

        if get_context == 'other':
            task_line_id.write({
                'other': True,
            })
        if line_id:
            emp = self._context['employee']
            res.write({
                'expense_id_worksheet_line': line_id,
                'employee_id': int(emp),
                'task_id_rec': task_line_id.project_task_id.id,
            })

        return res
