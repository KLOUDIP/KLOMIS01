# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.sale.wizard.sale_make_invoice_advance import SaleAdvancePaymentInv as SaleAdvancePaymentInvBase


def create_invoices(self):
    """Overload core method to pass refund value to sale order function"""
    sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))

    if self.advance_payment_method == 'delivered':
        sale_orders.with_context(refunded_amount=self.refunded_amount)._create_invoices(final=self.deduct_down_payments)
    else:
        # Create deposit product if necessary
        if not self.product_id:
            vals = self._prepare_deposit_product()
            self.product_id = self.env['product.product'].create(vals)
            self.env['ir.config_parameter'].sudo().set_param('sale.default_deposit_product_id', self.product_id.id)

        sale_line_obj = self.env['sale.order.line']
        for order in sale_orders:
            amount, name = self._get_advance_details(order)

            if self.product_id.invoice_policy != 'order':
                raise UserError(_(
                    'The product used to invoice a down payment should have an invoice policy set to "Ordered quantities". Please update your deposit product to be able to create a deposit invoice.'))
            if self.product_id.type != 'service':
                raise UserError(_(
                    "The product used to invoice a down payment should be of type 'Service'. Please use another product or update this product."))
            taxes = self.product_id.taxes_id.filtered(
                lambda r: not order.company_id or r.company_id == order.company_id)
            tax_ids = order.fiscal_position_id.map_tax(taxes, self.product_id, order.partner_shipping_id).ids
            context = {'lang': order.partner_id.lang}
            analytic_tag_ids = []
            for line in order.order_line:
                analytic_tag_ids = [(4, analytic_tag.id, None) for analytic_tag in line.analytic_tag_ids]

            so_line_values = self._prepare_so_line(order, analytic_tag_ids, tax_ids, amount)
            so_line = sale_line_obj.create(so_line_values)
            del context
            self._create_invoice(order, so_line, amount)
    if self._context.get('open_invoices', False):
        return sale_orders.action_view_invoice()
    return {'type': 'ir.actions.act_window_close'}


SaleAdvancePaymentInvBase.create_invoices = create_invoices


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
                    value = bool(order_lines.filtered(lambda x: x.qty_to_invoice < 0) and order_lines.filtered(
                        lambda x: x.coupon_program_id))
                    if value == True:
                        record.visible_refunded_amount = True
                    else:
                        record.visible_refunded_amount = False
                else:
                    record.visible_refunded_amount = False
            else:
                record.visible_refunded_amount = False
