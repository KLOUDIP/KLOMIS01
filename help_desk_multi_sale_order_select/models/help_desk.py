from odoo.osv import expression
from odoo import api, fields, models, tools, _


class HelpDeskSale(models.Model):
    _inherit = 'helpdesk.ticket'

    sale_order_ids = fields.Many2many('sale.order', string='Sales Order')
    helpdesk_ticket_ids_cou = fields.Integer(compute='_compute_ticket_ids')
    count = fields.Boolean(default=False)

    @api.onchange('count')
    def do_action(self):
        ids = self.sale_order_ids
        if ids:
            self.count = True
        else:
            self.count = False

    @api.depends('sale_order_ids')
    def _compute_ticket_ids(self):
        ids = self.sale_order_ids
        if ids:
            self.helpdesk_ticket_ids_cou = len(ids)
            self.count = True
        else:
            self.helpdesk_ticket_ids_cou = 0
            self.count = False

    def action_view_sale_ids(self):
        action = {
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.sale_order_ids.ids)],
            'view_mode': 'list,form',
            'name': _('Sale Orders'),
            'res_model': 'sale.order',
        }
        return action

    def action_open_helpdesk_pending_ticket(self):
        self.ensure_one()
        records = self.partner_ticket_ids.filtered(lambda ticket: not ticket.stage_id.fold)
        action = self.env["ir.actions.actions"]._for_xml_id("helpdesk.helpdesk_ticket_action_main_tree")
        action.update({
            'domain': [('id', '!=', self.id), ('id', 'in', records.ids)],
            'context': {'create': False},
        })
        return action
