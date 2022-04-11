from odoo import models, fields, api, _


class Expenses(models.Model):
    _inherit = 'hr.expense'

    expense_id_worksheet_line = fields.Many2one('worksheet.template.line', 'Worksheet Id')
    task_id_rec = fields.Many2one('project.task', 'Task Id')

    @api.model
    def create(self, vals):
        res = super(Expenses, self).create(vals)

        if res.expense_id_worksheet_line.id:
            line_id = self.env.context.get('active_id')
            task_line_id = self.env['worksheet.template.line'].search([('id', '=', line_id)])

            if 'product_val' in self._context:
                get_context = self._context['product_val']
            else:
                get_context = False

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

            if get_context == 'other_2':
                task_line_id.write({
                    'other_2': True,
                })

            if get_context == 'other_3':
                task_line_id.write({
                    'other_3': True,
                })

            if line_id:
                emp = self._context['default_employee']
                res.write({
                    'expense_id_worksheet_line': line_id,
                    'employee_id': int(emp),
                    'task_id_rec': task_line_id.project_task_id.id,
                })
        else:
            res.task_id_rec.write({'extra_minutes': True})
        return res

    @api.onchange('company_id')
    def _onchange_expense_company_id(self):
        if self.env.context.get('default_employee'):
            self.employee_id = self.env.context.get('default_employee')
        else:
            self.employee_id = self.env['hr.employee'].search(
                [('user_id', '=', self.env.uid), ('company_id', '=', self.company_id.id)])
