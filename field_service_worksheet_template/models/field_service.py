from odoo import models, fields, api, _
from ast import literal_eval
from odoo.exceptions import UserError

class WorksheetTemplateLine(models.Model):
    _name = 'worksheet.template.line'
    _inherit = ['portal.mixin']

    name = fields.Char('Name')
    template_id = fields.Many2one('project.worksheet.template', string='Template')
    select_user = fields.Many2one('res.users', string='Assigned to', required=True)
    fleet_id = fields.Many2one('fleet.vehicle', string='Fleet Code')
    project_task_id = fields.Many2one('project.task', string="Project Task")
    done_mark = fields.Boolean('Mark as Done')
    select_vals = fields.Boolean('Select')
    food = fields.Boolean('Mark as Done')
    extra = fields.Boolean('Mark as Done')
    beverage = fields.Boolean('Mark as Done')
    transport = fields.Boolean('Mark as Done')
    other = fields.Boolean('Mark as Done')
    other_2 = fields.Boolean('Mark as Done')
    other_3 = fields.Boolean('Mark as Done')
    line_add = fields.Boolean('Line Add')
    worksheet_id = fields.Integer('WorkSheet Id')
    expense_id = fields.One2many('hr.expense', 'expense_id_worksheet_line', string='Hr Expense')
    allow_worksheets = fields.Boolean(default=False)
    fsm_is_sent = fields.Boolean('Is Worksheet sent', readonly=True)
    customer_signature = fields.Binary('Signature', help='Signature received through the portal.', copy=False,
                                       attachment=True)
    customer_signed_by = fields.Char('Signed By', help='Name of the person that signed the task.', copy=False)

    technician_signature = fields.Binary('Signature', help='Signature received through the portal.', copy=False,
                                         attachment=True)
    technician_signed_by = fields.Char('Signed By', help='Name of the person that signed the task.', copy=False)

    @api.onchange('template_id')
    def _user_error(self):
        if self.line_add:
            raise UserError(_("This worksheet cannot change, you have already add this, if you want to change this, delete and add a new item "))

    def action_fsm_worksheet_template(self):
        template_id = self.template_id
        get_line_id = self.id
        worksheet_id = self.worksheet_id

        line_add = self.line_add
        match= []
        get_user = self.env['project.task'].search([('id', '=', self.project_task_id.id)]).worksheet_template_lines
        for rec in get_user:
            match.append((rec.select_user.id, rec.template_id.id))

        self = self.project_task_id
        if self.allow_billable:
            if self.allow_timesheets or self.allow_material:  # if material or time spent on task
                self._fsm_ensure_sale_order()

        action = template_id.action_id.read()[0]
        if line_add:
            worksheet = self.env[template_id.model_id.model].sudo().search([('x_studio_line_id', '=', get_line_id)])
        else:
            if len(match) == 1:
                worksheet = self.env[template_id.model_id.model].sudo().search([('x_studio_line_id', '=', get_line_id)])
            else:
                if len(match) != len(set(match)):
                    worksheet = self.env[template_id.model_id.model].sudo().search([('x_studio_line_id', '=', get_line_id)])
                else:
                    worksheet = self.env[template_id.model_id.model].sudo().search([('x_task_id', '=', 'not')])
        context = literal_eval(action.get('context', '{}'))
        action.update({
            'res_id': worksheet.id if worksheet else False,
            'views': [(False, 'form')],
            'context': {
                **context,
                'edit': True,
                'default_x_task_id': self.id,
                'default_x_studio_line_id': get_line_id,
                'form_view_initial_mode': 'edit',
            },
        })
        new_id = self.env['worksheet.template.line'].search([('id', '=', get_line_id)])
        new_id.write({
            'line_add': True,
            'worksheet_id': worksheet.id if worksheet else False
        })

        return action

    def action_form_worksheet_template(self):
        template_id = self.template_id
        get_line_id = self.id
        worksheet_id = self.worksheet_id
        action = template_id.action_id.read()[0]
        if get_line_id:
            worksheet = self.env[template_id.model_id.model].sudo().search([('x_studio_line_id', '=', get_line_id)])

            if worksheet:
                action = template_id.action_id.read()[0]
                context = literal_eval(action.get('context', '{}'))
                action.update({
                    'res_id': worksheet.sudo().id,
                    'views': [(False, 'form')],
                })

                return action
            else:
                raise UserError(_(
                    "This Template has no worksheet "))

    def action_to_create_expense_food(self):
        pro_id = False
        get_pro_id = self.env['product.product'].search([('name', '=', 'Meal Package')])
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
                'product_val': 'food',
                'default_employee_id': self.select_user.employee_id.id,
                'default_product_id': pro_id,
                'default_employee': self.select_user.employee_id.id,
                'default_expense_id_worksheet_line': self.id,
                'default_task_id_rec': self.project_task_id.id,

            },
            'flags': {'form': {'action_buttons': False}}

        }

    def action_to_create_expense_beverage(self):

        pro_id = False
        get_pro_id = self.env['product.product'].search([('name', '=', 'Night Out Package')])
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
                'product_val': 'beverage',
                'default_employee_id': self.select_user.employee_id.id,
                'default_employee': self.select_user.employee_id.id,
                'default_product_id': pro_id,
                'default_expense_id_worksheet_line': self.id,
                'default_task_id_rec': self.project_task_id.id,

            },
            'flags': {'form': {'action_buttons': False}}

        }

    def action_to_create_expense_extra_minutes(self):

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
                'default_employee_id': self.select_user.employee_id.id,
                'default_employee': self.select_user.employee_id.id,
                'default_product_id': pro_id,
                'default_expense_id_worksheet_line': self.id,
                'default_task_id_rec': self.project_task_id.id,

            },
            'flags': {'form': {'action_buttons': False}}

        }

    def action_to_create_expense_transport(self):

        pro_id = False
        get_pro_id = self.env['product.product'].search([('name', '=', 'Transport - Private Motorbike')])
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
                'product_val': 'transport',
                'default_employee_id': self.select_user.employee_id.id,
                'default_employee': self.select_user.employee_id.id,
                'default_product_id': pro_id,
                'default_expense_id_worksheet_line': self.id,
                'default_task_id_rec': self.project_task_id.id,

            },
            'flags': {'form': {'action_buttons': False}}

        }

    def action_to_create_expense_other(self):

        pro_id = False
        # get_pro_id = self.env['product.product'].search([('name', '=', 'Other')])
        # if get_pro_id:
        #     pro_id = get_pro_id.id

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
                # 'product_val': 'other',
                'product_val': self._context.get('product_val', False),
                'default_employee_id': self.select_user.employee_id.id,
                'default_employee': self.select_user.employee_id.id,
                'default_product_id': pro_id,
                'default_expense_id_worksheet_line': self.id,
                'default_task_id_rec': self.project_task_id.id,

            },
            'flags': {'form': {'action_buttons': False}}

        }

    def action_send_report_template(self):
        self.ensure_one()
        if not self.project_task_id:
            raise UserError(_("To send the report, you need to select a worksheet template."))

        # Note: as we want to see all time and material on worksheet, ensure the SO is created (case: timesheet but no material, the
        # time should be sold on SO)
        if self.project_task_id.allow_billable:
            self.project_task_id._fsm_ensure_sale_order()

        template_id = self.env.ref('field_service_worksheet_template.mail_template_data_send_report_custom').id
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': {
                'default_model': 'project.task',
                'default_res_id': self.project_task_id.id,
                'default_use_template': bool(template_id),
                'default_template_id': template_id,
                'force_email': True,
                'fsm_mark_as_sent': True,
            },
        }

    def action_worksheet_send(self):
        self.ensure_one()
        template_id = self.env.ref('field_service_worksheet_template.mail_template_data_send_report_custom1').id
        lang = self.env.context.get('lang')
        template = self.env['mail.template'].browse(template_id)
        #if template.lang:
            #lang = template._render_template(template.lang, 'worksheet.template.line', self.ids[0])
        ctx = {
            'default_model': 'worksheet.template.line',
            'default_res_id': self.id,
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'force_email': True,
            'fsm_mark_as_sent': True,
        }
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }

    def action_preview_worksheet(self):
        self.ensure_one()
        if not self.template_id:
            raise UserError(_("To send the report, you need to select a worksheet template."))

        # Note: as we want to see all time and material on worksheet, ensure the SO is created when (case: timesheet but no material, the time should be sold on SO)
        if self.project_task_id.allow_billable:
            if self.project_task_id.allow_timesheets or self.project_task_id.allow_material:
                # self.project_task_id.sudo()._reflect_timesheet_quantities()
                self.project_task_id._fsm_ensure_sale_order()

        source = 'fsm' if self.env.context.get('fsm_mode', False) else 'project'
        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': self.get_portal_url(suffix='/worksheet/%s' % source)
        }

    def _compute_access_url(self):
        super(WorksheetTemplateLine, self)._compute_access_url()
        for task in self:
            task.access_url = '/my/sheet/%s' % task.id

    def customer_has_to_be_signed(self):
        return not self.customer_signature

    def technician_has_to_be_signed(self):
        return not self.technician_signature

    def _get_report_base_filename(self):
        self.ensure_one()
        return 'Worksheet %s - %s' % (self.project_task_id.name, self.project_task_id.partner_id.name)

    @api.model
    def create(self, vals):
        if 'name' in vals:
            if vals['name'] == False:
                vals['name'] = self.env['ir.sequence'].next_by_code('worksheet.template.line', sequence_date=None) or _('New')
        result = super(WorksheetTemplateLine, self).create(vals)
        return result


