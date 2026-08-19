# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    auto_subscription_created = fields.Boolean(
        string='Auto Subscription Created',
        default=False,
        help='Technical field to track if a free subscription has been automatically created for this contact',
        copy=False
    )

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)

        # Find partners where 'is_trazet_user' was passed in vals and is True
        for vals, partner in zip(vals_list, partners):
            if vals.get('is_trazet_user') and not partner.parent_id and partner.type == 'contact':
                partner._create_free_subscription()

        return partners

    def _create_free_subscription(self):
        self.ensure_one()

        if self.auto_subscription_created:
            _logger.info(f"Free subscription already created for {self.name} (ID: {self.id})")
            return

        # Find free plan products
        free_plan_products = self.env['product.template'].search([
            ('is_free_plan', '=', True),
            ('recurring_invoice', '=', True),
            ('active', '=', True)
        ])

        if not free_plan_products:
            _logger.warning("No free plan subscription products found. Cannot create free subscription.")
            return

        # Find a subscription plan to use
        subscription_plan = self.env['sale.subscription.plan'].search([('is_free_plan', '=', True),
                                                                       ('active', '=', True)], limit=1)
        if not subscription_plan:
            _logger.warning("No subscription plan found. Cannot create free subscription.")
            return

        # Create subscription order
        try:
            SaleOrder = self.env['sale.order']
            OrderLine = self.env['sale.order.line']

            vals = {
                'partner_id': self.id,
                'partner_invoice_id': self.id,
                'partner_shipping_id': self.id,
                'plan_id': subscription_plan.id,
                'subscription_state': '1_draft',
                'is_subscription': True,
                'start_date': fields.Date.today(),
                'is_free_plan': True,
            }

            # Create the sale order
            subscription = SaleOrder.create(vals)

            # Keep track of current sequence number
            sequence = 10

            # Add order lines for the free plan products
            for product_template in free_plan_products:
                variant = product_template.product_variant_ids[:1]
                if not variant:
                    _logger.warning(f"No variants found for product {product_template.name}. Skipping.")
                    continue

                # Create the main product line
                main_line_vals = {
                    'order_id': subscription.id,
                    'product_id': variant.id,
                    'name': variant.name,
                    'product_uom_qty': 1,
                    'price_unit': 0.0,  # It's free!
                    'sequence': sequence,
                }
                main_line = OrderLine.create(main_line_vals)
                sequence += 10

                # For combo products, add the related combo items
                if product_template.type == 'combo' and product_template.combo_ids:
                    # Process each combo choice and its items
                    for combo in product_template.combo_ids:
                        # Find the default item for this combo choice
                        # In a typical selection, we'd use the one selected in the UI
                        # For automatic creation, we'll take the first item
                        default_item = combo.combo_item_ids[:1]
                        if not default_item:
                            continue

                        # Create a line for this combo item
                        item_product = default_item.product_id
                        uom_quantity = 1
                        # For combo items, also check if they should have quantity 2 for devicesGroups
                        if item_product.trazet_product_key == 'devicesGroups':
                            uom_quantity = 2
                            _logger.info(f"Setting quantity to 2 for devicesGroups combo item: {item_product.name}")

                        combo_line_vals = {
                            'order_id': subscription.id,
                            'product_id': item_product.id,
                            'name': item_product.name,
                            'product_uom_qty': uom_quantity,  # Multiply by the combo item quantity * default_item.quantity
                            'price_unit': 0.0,  # It's free!
                            'sequence': sequence,
                            # Link to the main combo line
                            'linked_line_id': main_line.id,
                            'combo_item_id': default_item.id,
                        }
                        OrderLine.create(combo_line_vals)
                        sequence += 10

            # CRITICAL FIX: Confirm the subscription with a context flag to prevent free plan closure
            subscription.with_context(skip_free_plan_closure=True).action_confirm()

            # Stabilize line quantities to prevent changes after creation
            # This is a critical step for free subscriptions
            for line in subscription.order_line:
                # Mark the line as fully invoiced to prevent quantity changes
                line.qty_invoiced = line.product_uom_qty
                line.qty_to_invoice = 0
                # Force the invoice status to be 'invoiced'
                line.with_context(skip_line_status_compute=True).invoice_status = 'invoiced'

            # Create a dummy $0 invoice to satisfy the subscription engine
            # This step is optional but helps with more complex subscription scenarios
            try:
                invoice = subscription._create_invoices()
                if invoice:
                    invoice.action_post()
                    # Link the invoice to all subscription lines
                    for line in subscription.order_line:
                        line.invoice_lines = [(4, invoice_line.id) for invoice_line in invoice.invoice_line_ids]
            except Exception as invoice_error:
                _logger.warning(f"Could not create invoice for free subscription: {str(invoice_error)}")

            self.write({'auto_subscription_created': True})

            _logger.info(f"Successfully created free subscription {subscription.name} for {self.name} (ID: {self.id})")

        except Exception as e:
            _logger.error(f"Failed to create free subscription for {self.name} (ID: {self.id}): {str(e)}")

