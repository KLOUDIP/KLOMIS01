# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def can_decrease_quantity(self):
        """Check if line quantity can be decreased"""
        self.ensure_one()
        return (self.recurring_invoice and
                self.order_id.is_subscription and
                self.order_id.subscription_state in ['3_progress', '4_paused'] and
                self.product_uom_qty > 1 and not self.linked_line_id)

    def prepare_decreased_line_values(self, new_qty):
        """Prepare values for line with decreased quantity"""
        self.ensure_one()
        if new_qty <= 0 or new_qty >= self.product_uom_qty:
            return False

        return {
            'product_id': self.product_id.id,
            'name': self.name,
            'product_uom_qty': new_qty,
            'product_uom_id': self.product_uom_id.id,
            'price_unit': self.price_unit,
            'discount': self.discount,
            'order_id': self.order_id.id
        }

    def _get_renew_upsell_values(self, subscription_state):
        """
        Override to exclude per-subscription products (allowExternalAPI, collectPeriod)
        from upsell orders if they already exist in the parent subscription with qty > 0.

        Odoo Standard Behavior:
        - When creating upsell order, ALL lines from parent subscription are copied
        - Each line gets product_uom_qty: 0
        - User can then increase quantities as needed

        Our Custom Behavior:
        - allowExternalAPI and collectPeriod are per-subscription (can only have 0 or 1)
        - If parent subscription already has these products with qty > 0:
          → Don't include them in the upsell order at all
          → User cannot add/increase them
        - If parent subscription doesn't have them or has qty = 0:
          → Include them normally
          → User can add them (limited to qty 1)

        This prevents confusion and enforces business rule:
        "These products can only be added once per subscription"
        """
        # Get standard order lines from parent method
        order_lines = super()._get_renew_upsell_values(subscription_state)

        # Only apply filtering for upsell orders (not renewal)
        if subscription_state != '7_upsell':
            return order_lines

        # Find per-subscription products that exist in parent subscription with qty > 0
        # These should NOT be copied to the upsell order
        existing_per_subscription_lines = self.filtered(
            lambda l: l.recurring_invoice
                      and l.product_id.trazet_product_key in ['allowExternalAPI', 'collectPeriod']
                      and l.product_uom_qty > 0
        )

        # If no per-subscription products exist in parent, no filtering needed
        if not existing_per_subscription_lines:
            return order_lines

        # Get product IDs to exclude from upsell order
        excluded_product_ids = existing_per_subscription_lines.mapped('product_id').ids
        excluded_product_names = existing_per_subscription_lines.mapped('product_id.name')

        _logger.info(
            f"Creating upsell order: Excluding per-subscription products that already exist in parent: "
            f"{', '.join(excluded_product_names)}"
        )

        # Filter order_lines to exclude products that already exist in parent
        # order_lines format: [(0, 0, {...}), (0, 0, {...}), ...]
        filtered_lines = []

        for line_command in order_lines:
            # Check if this is a create command: (0, 0, {...})
            if line_command[0] == 0 and line_command[1] == 0:
                line_vals = line_command[2]
                product_id = line_vals.get('product_id')

                # Skip this line if it's for an excluded product
                if product_id in excluded_product_ids:
                    product_name = self.env['product.product'].browse(product_id).name
                    _logger.info(
                        f"Upsell order: Excluded line for '{product_name}' "
                        f"(already exists in parent subscription with qty > 0)"
                    )
                    continue  # Don't add this line to filtered_lines

            # Keep all other lines (including display lines, notes, etc.)
            filtered_lines.append(line_command)

        _logger.info(
            f"Upsell order creation: Filtered {len(order_lines) - len(filtered_lines)} lines, "
            f"kept {len(filtered_lines)} lines"
        )

        return filtered_lines

    def write(self, vals):
        """
        Prevent setting quantity > 1 for allowExternalAPI and collectPeriod
        """
        if 'product_uom_qty' in vals:
            for line in self:
                trazet_key = line.product_id.product_tmpl_id.trazet_product_key

                if trazet_key in ['allowExternalAPI', 'collectPeriod']:
                    new_qty = vals.get('product_uom_qty')

                    if new_qty > 1:
                        vals['product_uom_qty'] = 1
                        _logger.info(
                            f"Auto-adjusted {line.product_id.name} quantity from {new_qty} to 1 "
                            f"(per-subscription feature limit) - via write method"
                        )

        return super(SaleOrderLine, self).write(vals)