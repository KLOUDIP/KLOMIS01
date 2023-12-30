# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.addons.sale.wizard.sale_make_invoice_advance import SaleAdvancePaymentInv as SaleAdvancePaymentInvBase


def _create_invoices(self, sale_orders):
    """
    @overload - pass refund value to sale order function
    """
    self.ensure_one()
    if self.advance_payment_method == 'delivered':
        return sale_orders.with_context(refunded_amount=self.refunded_amount)._create_invoices(final=self.deduct_down_payments)
    else:
        self.sale_order_ids.ensure_one()
        self = self.with_company(self.company_id)
        order = self.sale_order_ids

        # Create deposit product if necessary
        if not self.product_id:
            self.product_id = self.env['product.product'].create(
                self._prepare_down_payment_product_values()
            )
            self.env['ir.config_parameter'].sudo().set_param(
                'sale.default_deposit_product_id', self.product_id.id)

        # Create down payment section if necessary
        if not any(line.display_type and line.is_downpayment for line in order.order_line):
            self.env['sale.order.line'].create(
                self._prepare_down_payment_section_values(order)
            )

        down_payment_so_line = self.env['sale.order.line'].create(
            self._prepare_so_line_values(order)
        )

        invoice = self.env['account.move'].sudo().create(
            self._prepare_invoice_values(order, down_payment_so_line)
        ).with_user(self.env.uid)  # Unsudo the invoice after creation

        invoice.message_post_with_view(
            'mail.message_origin_link',
            values={'self': invoice, 'origin': order},
            subtype_id=self.env.ref('mail.mt_note').id)

        return invoice


SaleAdvancePaymentInvBase._create_invoices = _create_invoices


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    refunded_amount = fields.Monetary(string='Amount To Be Charged')
    visible_refunded_amount = fields.Boolean(string='Visible Refunded Amount', help='For UI Purposes',
                                             compute="_check_coupon_visibility")

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
