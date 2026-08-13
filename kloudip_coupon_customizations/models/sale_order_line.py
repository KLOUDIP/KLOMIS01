# -*- coding: utf-8 -*-

from odoo import api, fields, models, _, Command
from odoo.exceptions import AccessError, UserError
from odoo.tools.float_utils import float_is_zero


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _prepare_invoice_line(self, **optional_values):
        self.ensure_one()

        vals = super()._prepare_invoice_line(**optional_values)

        if self.display_type:
            return vals

        if not self.product_id:
            return vals

        if not vals.get("account_id"):
            account = (
                    self.product_id.property_account_income_id
                    or self.product_id.categ_id.property_account_income_categ_id
            )

            if not account:
                raise UserError(_(
                    "Cannot create invoice: The product '%s' is missing an Income Account.\n\n"
                    "Please configure an Income Account on the product or its product category."
                ) % self.product_id.display_name)

            vals["account_id"] = account.id

        return vals

    @api.depends('qty_invoiced', 'qty_delivered', 'product_uom_qty', 'state')
    def _compute_qty_to_invoice(self):
        """ Clean Odoo 19 Override """
        super()._compute_qty_to_invoice()
        for line in self:
            reward_line = line.order_id.order_line.filtered(lambda x: x.is_reward_line)
            product_line = line.order_id.order_line.filtered(
                lambda x: x.product_id.id in reward_line.reward_id.discount_product_ids.ids)

            if (reward_line and (line.product_id.id in reward_line.reward_id.discount_product_ids.ids)) or (
                    line.product_id.id == reward_line.reward_id.discount_line_product_id.id):
                reward_line.qty_to_invoice = product_line.qty_delivered - product_line.qty_invoiced

    @api.depends('invoice_lines.move_id.state', 'invoice_lines.quantity')
    def _compute_qty_invoiced(self):
        """ Clean Odoo 19 Override """
        super()._compute_qty_invoiced()
        for line in self:
            qty_invoiced = 0.0
            invoice_lines = line._get_invoice_lines()
            invoice_lines = invoice_lines.filtered(lambda x: not x.move_id.refund_move)

            for invoice_line in invoice_lines:
                if invoice_line.move_id.state != 'cancel' or invoice_line.move_id.payment_state == 'invoicing_legacy':
                    if invoice_line.move_id.move_type == 'out_invoice':
                        qty_invoiced += invoice_line.product_uom_id._compute_quantity(
                            invoice_line.quantity, line.product_uom_id)
                    elif invoice_line.move_id.move_type == 'out_refund':
                        qty_invoiced -= invoice_line.product_uom_id._compute_quantity(
                            invoice_line.quantity, line.product_uom_id)

            line.qty_invoiced = qty_invoiced
