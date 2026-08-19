# -*- coding: utf-8 -*-
from odoo import models


class SaleOrder(models.Model):
    """Apply the combo item's custom `product_quantity` multiplier when building/updating
    website cart lines, since Odoo 19's website_sale no longer routes combo cart creation
    through a custom controller (see removed `/website_sale/combo_configurator/update_cart`).
    """
    _inherit = 'sale.order'

    def _prepare_order_line_values(self, product_id, quantity, uom_id, *, combo_item_id=None, **kwargs):
        if combo_item_id:
            combo_item = self.env['product.combo.item'].browse(combo_item_id)
            if combo_item.product_quantity and combo_item.product_quantity != 1:
                quantity = quantity * combo_item.product_quantity
        return super()._prepare_order_line_values(
            product_id, quantity, uom_id, combo_item_id=combo_item_id, **kwargs
        )

    def _cart_update_order_line(self, order_line, quantity, **kwargs):
        combo_item_lines = order_line.linked_line_ids.filtered('combo_item_id')
        multiplied_items = combo_item_lines.filtered(lambda l: l.combo_item_id.product_quantity != 1)
        if order_line.product_type != 'combo' or not multiplied_items:
            return super()._cart_update_order_line(order_line, quantity, **kwargs)

        self.ensure_one()
        order_line.ensure_one()

        if quantity <= 0:
            order_line.unlink()
            return self.env['sale.order.line']

        update_values = self._prepare_order_line_update_values(order_line, quantity, **kwargs)
        if update_values and 'product_uom_qty' in update_values:
            combo_quantity = quantity
            for item_line in combo_item_lines:
                multiplier = item_line.combo_item_id.product_quantity or 1.0
                target_item_qty = quantity * multiplier
                if target_item_qty != item_line.product_uom_qty:
                    verified_item_qty, _warning = self._verify_updated_quantity(
                        item_line, item_line.product_id.id, target_item_qty,
                        uom_id=item_line.product_uom_id.id, **kwargs
                    )
                    combo_quantity = min(combo_quantity, verified_item_qty / multiplier)

            for item_line in combo_item_lines:
                multiplier = item_line.combo_item_id.product_quantity or 1.0
                expected_item_qty = combo_quantity * multiplier
                if expected_item_qty != item_line.product_uom_qty:
                    self.with_context(skip_cart_verification=True)._cart_update_line_quantity(
                        line_id=item_line.id, quantity=expected_item_qty
                    )
            update_values['product_uom_qty'] = combo_quantity

        if update_values:
            order_line.write(update_values)
            order_line._check_validity()

        return order_line