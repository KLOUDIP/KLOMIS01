# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class SubscriptionAdvancePaymentInv(models.TransientModel):
    _name = "subscription.advance.payment.inv"

    currency_id = fields.Many2one(
        comodel_name='res.currency',
        compute='_compute_currency_id',
        store=True)
    sale_order_ids = fields.Many2many(
        'sale.order', default=lambda self: self.env.context.get('active_ids'))
    count = fields.Integer(string="Order Count", compute='_compute_count')
    refunded_amount = fields.Monetary(string='Amount To Be Charged')
    visible_refunded_amount = fields.Boolean(string='Visible Refunded Amount', help='For UI Purposes',
                                             compute="_check_coupon_visibility")

    def create_subscription_invoices(self):
        orders = self.sale_order_ids
        account_move = orders.with_context(refunded_amount=self.refunded_amount)._create_recurring_invoice()
        if account_move:
            return orders.action_view_invoice()
        else:
            raise UserError(orders._nothing_to_invoice_error_message())

    @api.depends('sale_order_ids')
    def _compute_currency_id(self):
        self.currency_id = False
        for wizard in self:
            if wizard.count == 1:
                wizard.currency_id = wizard.sale_order_ids.currency_id

    @api.depends('sale_order_ids')
    def _compute_count(self):
        for wizard in self:
            wizard.count = len(wizard.sale_order_ids)

    @api.depends('refunded_amount')
    def _check_coupon_visibility(self):
        for record in self:
            active_id = self.env.context.get('active_id')
            active_model = self.env.context.get('active_model')
            if active_model == 'sale.order':
                sale_object = self.env['sale.order'].browse(active_id)
                if sale_object:
                    order_lines = sale_object.order_line
                    value = bool(order_lines.filtered(lambda x: x.qty_to_invoice < 0) and order_lines.filtered(lambda x: x.reward_id))
                    if value:
                        record.visible_refunded_amount = True
                    else:
                        record.visible_refunded_amount = False
                else:
                    record.visible_refunded_amount = False
            else:
                record.visible_refunded_amount = False
