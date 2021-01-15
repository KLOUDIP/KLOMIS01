from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ProjectTaskLine(models.Model):
    _inherit = 'project.task'

    worksheet_template_lines = fields.One2many('worksheet.template.line', 'project_task_id', string='WorkSheet Lines', copy=True)
    mark_as_done_rec = fields.Boolean()
    helpdesk_ticket_ids_cou = fields.Integer(compute='_compute_ticket_ids')
    related_task = fields.Many2one('project.task')
    tech_team_member_id = fields.Many2one("res.users", "TECH Team Member")
    count = fields.Boolean()
    accessible = fields.Boolean(compute='_compute_cordinator_group')
    extra_minutes = fields.Boolean("Extra Minutes")

    def _compute_cordinator_group(self):
        for i in self:
            if i.env.user.has_group('field_service_worksheet_template.group_coordinator_fsm') or i.env.user.has_group('industry_fsm.group_fsm_manager'):
                i.accessible = True
            else:
                i.accessible = False

    def _compute_ticket_ids(self):
        ids = self.env['helpdesk.ticket'].sudo().search([('help_desk_ticket_id', '=', self.id)])
        if ids:
            self.helpdesk_ticket_ids_cou = len(ids)
            self.count = True
        else:
            self.helpdesk_ticket_ids_cou = 0
            self.count = False

    def action_for_helpdesk_ticket(self):
        action = self.env.ref('helpdesk.helpdesk_ticket_action_main_tree').read()[0]
        action['context'] = {}
        action['domain'] = [('help_desk_ticket_id', 'child_of', self.ids)]
        return action

    def action_task_temp(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create a Field Service HelpDesk ticket'),
            'res_model': 'ticket.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    def action_fsm_validate(self):
        """ Moves Task to next stage.
            If allow billable on task, timesheet product set on project and user has privileges :
            Create SO confirmed with time and material.
        """

        get_worksheet_lines = self.worksheet_template_lines
        vals = False
        if get_worksheet_lines:
            lines = self.worksheet_template_lines.mapped('done_mark')
            vals = [i for i, val in enumerate(lines) if not val]
        else:
            raise UserError(_(
                "Please Add worksheet lines, Otherwise you can not complete this task"))

        if vals or vals:
            raise UserError(_("Please Check the worksheet lines, all of have mark as done, otherwise you can not complete this task"))
        else:
            for task in self:
                task.write({
                    'mark_as_done_rec': True
                })
                # determine closed stage for task
                closed_stage = task.project_id.type_ids.filtered(lambda stage: stage.is_closed)
                if not closed_stage and len(task.project_id.type_ids) > 1:  # project without stage (or with only one)
                    closed_stage = task.project_id.type_ids[-1]

                values = {'fsm_done': True}
                if closed_stage:
                    values['stage_id'] = closed_stage.id

                if task.allow_billable:
                    if task.allow_timesheets or task.allow_material:
                        task._fsm_ensure_sale_order()
                        if task.sudo().sale_order_id.state in ['draft', 'sent']:
                            task.sudo().sale_order_id.action_confirm()

                task.write(values)

    def action_create_new_task(self):
        get_ids = self.mapped('worksheet_template_lines').filtered(lambda x: x.select_vals == True)
        if not get_ids:
            raise UserError(_(
                "Please Select at least one Worksheet"))
        else:
            get_mark_as_done = get_ids.filtered(lambda x: x.done_mark == True)
            if get_mark_as_done:
                raise UserError(_(
                    "You can not add mark as done worksheet(s) to create a new task."))
            else:
                count = self.search_count([('name', 'like', self.name)])
                if count == 0:
                    count = ""
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Create a Field Task'),
                    'res_model': 'task.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'product_val': 'transport',
                        'default_name': self.name + '-' + str(count),
                        'default_partner_id': self.partner_id.id,
                        'fsm_task_ids': self.id,

                    },
                }

    def get_extra_minutes_expenses(self):
        pro_id = False
        get_pro_id = self.env['product.product'].search([('name', '=', 'Excess Work Minutes')])
        if get_pro_id:
            pro_id = get_pro_id.id

        return {
            'name': _('EXPENSE view'),
            'view_mode': 'form',
            'view_id': False,
            'edit': False,
            'view_type': 'form',
            'res_model': 'hr.expense',
            'res_id': False,
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
            'domain': '[]',
            'context': {
                'product_val': 'extra',
                'default_employee_id': self.tech_team_member_id.employee_id.id,
                'default_employee': self.tech_team_member_id.employee_id.id,
                'default_product_id': pro_id,
                'default_expense_id_worksheet_line': False,
                'default_task_id_rec': self.id,
            },
            'flags': {'form': {'action_buttons': False}}
        }