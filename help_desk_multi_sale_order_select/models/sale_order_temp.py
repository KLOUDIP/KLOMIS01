from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    ticket_id = fields.Many2one('helpdesk.ticket', string='HelpDesk ticket', groups="sales_team.group_sale_salesman,account.group_account_invoice")
    sale_order_ids = fields.One2many('sale.order', 'ticket_id', string='Sales Order',
                                     groups="sales_team.group_sale_salesman,account.group_account_invoice")
    tickets = fields.Many2many('helpdesk.ticket', string='HelpDesk ticket')

    helpdesk_ticket_ids_cou = fields.Integer(compute='_compute_ticket_ids')
    count = fields.Boolean(Default=False)

    def _compute_ticket_ids(self):
        ids = self.tickets
        if ids:
            self.helpdesk_ticket_ids_cou = len(ids)
            self.count = True
        else:
            self.helpdesk_ticket_ids_cou = 0
            self.count = False

    def action_view_tickets_ids(self):

        action = {
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.tickets.ids)],
            'view_mode': 'list,form',
            'name': _('HelpDesk Tickets'),
            'res_model': 'helpdesk.ticket',
        }
        return action
