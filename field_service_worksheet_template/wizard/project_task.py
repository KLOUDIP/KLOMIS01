from odoo import api, fields, models, _


class FreightWizard(models.TransientModel):
    _name = 'task.wizard'

    def _default_task_tmpl(self):
        return self.env['project.task'].browse(self._context.get('active_id'))

    current_task_tmpl_id = fields.Many2one('project.task', default=_default_task_tmpl)
    help_desk_ticket_id = fields.Many2one('helpdesk.ticket', string="Select/Create Ticket")
    select_created_helpdesk_ticket = fields.Boolean('Select a  Helpdesk Ticket')
    name = fields.Char('Task name')
    partner_id = fields.Many2one('res.partner', 'Customer')

    def action_task_view(self):
        line_ids = self.current_task_tmpl_id.mapped('worksheet_template_lines').filtered(lambda x: x.select_vals == True)
        new_task = self.env['project.task'].create(
            {
                'name': self.name,
                'partner_id': self.partner_id.id,
                'related_task': self.current_task_tmpl_id.id,
                'helpdesk_ticket_id': self.current_task_tmpl_id.helpdesk_ticket_id.id,
                'project_id': self.current_task_tmpl_id.project_id.id,
            }
        )
        if line_ids:
            for rec in line_ids:
                new_task.write({
                    'worksheet_template_lines': [(0, 0, {
                        'template_id': rec.template_id.id,
                        'select_user': rec.select_user.id,

                    })],
                })
                rec.unlink()
            return {
                'type': 'ir.actions.act_window',
                'name': _('Task'),
                'res_model': 'project.task',
                'view_mode': 'form',
                'view_id': self.env.ref('industry_fsm.project_task_view_form').id,
                'res_id': new_task.id,
                'target': 'current',
            }
        line_ids.unlink()
        print('done')