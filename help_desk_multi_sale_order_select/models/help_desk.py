from odoo import models, fields, api, _
import re


class HelpDeskSale(models.Model):
    _inherit = 'helpdesk.ticket'


    sale_order_ids = fields.Many2many('sale.order', string='Sales Order')
    helpdesk_ticket_ids_cou = fields.Integer(compute='_compute_ticket_ids')
    count = fields.Boolean(Default=False)

    @api.onchange('count')
    def do_action(self):
        ids = self.sale_order_ids
        if ids:
            self.count = True
        else:
            self.count = False

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

    @api.depends('partner_id')
    def _compute_partner_ticket_count(self):
        data = self.env['helpdesk.ticket'].read_group([
            ('partner_id', 'in', self.mapped('partner_id').ids),
            ('stage_id.is_close', '=', False)
        ], ['partner_id'], ['partner_id'], lazy=False)
        ticket_per_partner_map = dict((item['partner_id'][0], item['__count']) for item in data)
        records = self.env['helpdesk.ticket'].search([('partner_id', 'in', self.mapped('partner_id').ids),
                                                      ('stage_id.is_close', '=', False)])
        for ticket in self:
            ticket.partner_ticket_count = ticket_per_partner_map.get(ticket.partner_id.id, 0)
            ticket.partner_ticket_ids = records.filtered(lambda x: x.partner_id == ticket.partner_id.id)

    def action_open_helpdesk_ticket(self):
        records = self.env['helpdesk.ticket'].search([('partner_id', 'in', self.mapped('partner_id').ids),
                                                      ('stage_id.is_close', '=', False)])
        action = self.env["ir.actions.actions"]._for_xml_id("helpdesk.helpdesk_ticket_action_main_tree")
        if len(records) > 1:
            action['domain'] = [('id', 'in', records.ids)]
            return action

    # def write(self, vals):
    #     res = super(HelpDeskSale, self).write(vals)
    #     if 'sale_order_ids' in vals:
    #         if vals['sale_order_ids'][0]:
    #             for ids in vals['sale_order_ids']:
    #                 if ids[0] == 3:
    #                     sale_id = self.env['sale.order'].search([('id', '=', ids[1])])
    #                     text_vals = ''
    #                     list_val = []
    #                     tickets_name = (sale_id.tickets.split(","))
    #                     without_whitespace = [x.strip(' ') for x in tickets_name]
    #                     [list_val.append(x) for x in without_whitespace if x not in list_val]
    #                     remove_element = set(list_val) & set(self.name.split(","))
    #                     if remove_element:
    #                         list_val.remove(list(remove_element)[0])
    #                     count = False
    #                     for rec in list_val:
    #                         count += 1
    #                         if count == 1:
    #                             text_vals += rec
    #                         else:
    #                             text_vals += ', ' + rec
    #                     sale_id.write({
    #                         'tickets': ''
    #                     })
    #
    #                     sale_id.write({
    #                         'tickets': text_vals
    #                     })
    #                     print(ids)
    #
    #                 else:
    #                     for rec in self.sale_order_ids:
    #                         sale_id = self.env['sale.order'].search([('id', '=', rec.id)])
    #                         text_vals = ''
    #                         list_val = []
    #                         if sale_id.tickets:
    #                             ticket_names = (sale_id.tickets.split(","))
    #                             without_whitespace = [x.strip(' ') for x in ticket_names]
    #                             [list_val.append(x) for x in without_whitespace if x not in list_val]
    #                             count = False
    #                             for rec in list_val:
    #                                 count += 1
    #                                 if count == 1:
    #                                     text_vals += self.name + ', ' + rec
    #                                 else:
    #                                     text_vals += ', ' + rec
    #                             sale_id.write({
    #                                 'tickets': ''
    #                             })
    #
    #                             sale_id.write({
    #                                 'tickets': text_vals
    #                             })
    #
    #                         else:
    #                             sale_id.write({
    #                                 'tickets': self.name
    #                             })
    #
    #     return res
    #
    # @api.model_create_multi
    # def create(self, list_value):
    #     res = super(HelpDeskSale, self).create(list_value)
    #     if 'sale_order_ids' in list_value[0]:
    #         for rec in list_value[0]['sale_order_ids'][0][2]:
    #             sale_id = self.env['sale.order'].search([('id', '=', rec)])
    #             text_vals = ''
    #             list_val = []
    #             if sale_id.tickets:
    #                 ticket_names = (sale_id.tickets.split(","))
    #                 without_whitespace = [x.strip(' ') for x in ticket_names]
    #                 [list_val.append(x) for x in without_whitespace if x not in list_val]
    #                 count = False
    #                 for rec in list_val:
    #                     count += 1
    #                     if count == 1:
    #                         text_vals += list_value[0]['name'] + ', ' + rec
    #                     else:
    #                         text_vals += ', ' + rec
    #                 sale_id.write({
    #                     'tickets': ''
    #                 })
    #
    #                 sale_id.write({
    #                     'tickets': text_vals
    #                 })
    #
    #             else:
    #                 sale_id.write({
    #                     'tickets': res.name
    #                 })
    #
    #     return res