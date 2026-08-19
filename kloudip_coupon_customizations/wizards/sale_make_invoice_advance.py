# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    refunded_amount = fields.Monetary(string='Amount To Be Charged')
    visible_refunded_amount = fields.Boolean(
        string='Visible Refunded Amount',
        help='For UI Purposes',
        compute="_check_coupon_visibility"
    )

    def _create_invoices(self, sale_orders):

        sale_orders = sale_orders.with_context(refunded_amount=self.refunded_amount)
        return super(SaleAdvancePaymentInv, self)._create_invoices(sale_orders)

    @api.depends('refunded_amount')
    def _check_coupon_visibility(self):
        for record in self:
            record.visible_refunded_amount = False
            active_id = self.env.context.get('active_id')
            active_model = self.env.context.get('active_model')

            if active_model == 'sale.order' and active_id:
                sale_object = self.env['sale.order'].browse(active_id)
                if sale_object.exists():
                    order_lines = sale_object.order_line
                    if any(x.qty_to_invoice < 0 for x in order_lines) and any(x.reward_id for x in order_lines):
                        record.visible_refunded_amount = True
