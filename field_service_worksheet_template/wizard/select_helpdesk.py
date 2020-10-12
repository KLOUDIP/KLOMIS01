from odoo import api, fields, models, _


class FreightWizard(models.TransientModel):
    _name = 'ticket.wizard'

    def _default_task_tmpl(self):
        return self.env['project.task'].browse(self._context.get('active_id'))

    current_task_tmpl_id = fields.Many2one('project.task', default=_default_task_tmpl)
    help_desk_ticket_id = fields.Many2one('helpdesk.ticket', string="Select/Create Ticket")
    select_created_helpdesk_ticket = fields.Boolean('Select a  Helpdesk Ticket')

    def action_ticket_view(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create a Field Service HelpDesk ticket'),
            'res_model': 'helpdesk.ticket',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.current_task_tmpl_id.partner_id.id if self.current_task_tmpl_id.partner_id else False,
                'default_user_id': self.current_task_tmpl_id.user_id.id if self.current_task_tmpl_id.user_id else False,
                'default_help_desk_ticket_id': self.current_task_tmpl_id.id if self.current_task_tmpl_id else False,
            }
        }

    def action_for_created_ticket(self):
        self.help_desk_ticket_id.write({
            'help_desk_ticket_id': self.current_task_tmpl_id.id if self.current_task_tmpl_id.id else False,
            'partner_id': self.current_task_tmpl_id.partner_id.id if self.current_task_tmpl_id.partner_id.id else False,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create a Field Service HelpDesk ticket'),
            'res_model': 'helpdesk.ticket',
            'view_mode': 'form',
            'res_id': self.help_desk_ticket_id.id,
            'target': 'current',
        }