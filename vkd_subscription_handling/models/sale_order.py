import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Only a write that actually changes the *content* of the order may trigger a
# rebuild of the optional-products block. Bookkeeping writes - the ones
# _create_recurring_invoice() and the invoicing cron perform on
# next_invoice_date / invoice_status / last_invoice_date - must never do so.
OPTIONAL_TRIGGER_FIELDS = {'order_line', 'plan_id', 'partner_id', 'pricelist_id'}


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_quantity_decrease = fields.Boolean(
        string='Is Quantity Decrease',
        help='Indicates this order represents a quantity decrease from a subscription',
        default=False,
        copy=False,
    )

    def write(self, vals):
        res = super().write(vals)

        # Guard 1 - recursion: creating the block itself writes on the order.
        if self.env.context.get('skip_optional_products'):
            return res
        # Guard 2 - only content-changing writes may rebuild the block.
        if not (OPTIONAL_TRIGGER_FIELDS & set(vals)):
            return res

        for order in self:
            order._sync_optional_products()
        return res

    def _allow_optional_products(self):
        """Whether the optional-products block belongs on this order.

        The block is a *sales* tool: it lets a salesperson hand a customer a
        quotation with add-ons they can tick. It must never be built on an
        order the customer is driving themselves, because in Odoo 19 optional
        products are plain ``sale.order.line`` records - so anything added here
        shows up in the eCommerce cart, in checkout and in the portal exactly
        like a product the customer chose.
        """
        self.ensure_one()

        # Confirmed orders / subscriptions in progress are not being quoted.
        if self.state != 'draft':
            return False

        # eCommerce: a draft order carrying a website_id IS the customer's live
        # cart. Injecting lines into it is what made every product show up on
        # /shop/cart and blocked online ordering.
        if self.website_id:
            return False

        # Belt and braces: only an internal user preparing a quotation may
        # trigger this. Portal/public writes (cart updates, portal "add to my
        # subscription", payment callbacks) run as the public or portal user
        # even when sudo'ed, so this also covers website flows that reach
        # sale.order without a website_id.
        if not self.env.user._is_internal():
            return False

        if not self.is_subscription or not self.order_line:
            return False

        if self._get_optional_products_section():
            return False

        subscription_lines = self.order_line.filtered(
            lambda l: l.product_id.recurring_invoice)
        if not subscription_lines:
            return False

        # Free plans get no upsell block.
        has_free_plan_products = any(
            line.product_id.product_tmpl_id.is_free_plan
            or getattr(line.product_id.product_tmpl_id, 'is_fios_free_plan', False)
            for line in subscription_lines
        )
        if has_free_plan_products:
            return False

        return True

    def _sync_optional_products(self):
        """Add the optional-products block, but only where it belongs."""
        self.ensure_one()
        if not self._allow_optional_products():
            return
        self._add_optional_products()

    def _get_optional_products_section(self):
        """The 'Optional Products' feature no longer uses a separate `sale.order.option`
        model/`sale_order_option_ids` field (removed in v19). Optional products are now
        regular order lines living under an `is_optional` section line.
        """
        self.ensure_one()
        return self.order_line.filtered(lambda l: l.display_type == 'line_section' and l.is_optional)[:1]

    def _detect_subscription_platform(self):
        """Return 'fios', 'trazet' or False from the subscription's current
        recurring service lines, so optional products stay on the same platform
        (a FIOS subscription must not offer Trazet products and vice versa)."""
        self.ensure_one()
        has_fios = 'fios_service' in self.env['product.template']._fields
        recurring = self.order_line.filtered(
            lambda l: l.recurring_invoice and not l.display_type)
        for line in recurring:
            tmpl = line.product_id.product_tmpl_id
            if has_fios and tmpl.fios_service:
                return 'fios'
            if tmpl.trazet_product_key:
                return 'trazet'
        return False

    def _add_optional_products(self):
        self.ensure_one()

        # Get all potential optional products (excluding free plans and combos)
        all_optional_products = self.env['product.product'].search([
            ('recurring_invoice', '=', True),
            ('is_free_plan', '=', False),
            ('type', '!=', 'combo'),
            ('sale_ok', '=', True),
        ])

        # Only offer optional products of the SAME platform as this subscription:
        # a FIOS subscription gets FIOS products (fios_service), a Trazet one gets
        # Trazet products (trazet_product_key). Prevents mixing the two.
        platform = self._detect_subscription_platform()
        if platform == 'fios':
            all_optional_products = all_optional_products.filtered(
                lambda p: p.product_tmpl_id.fios_service)
        elif platform == 'trazet':
            all_optional_products = all_optional_products.filtered(
                lambda p: p.product_tmpl_id.trazet_product_key)

        # Get per-subscription products that already exist with qty > 0
        existing_trazet_keys = self.order_line.filtered(
            lambda l: l.recurring_invoice
                      and l.product_id.trazet_product_key in ['allowExternalAPI', 'collectPeriod']
                      and l.product_uom_qty > 0
        ).mapped('product_id.trazet_product_key')

        # Filter out products that already exist in subscription
        optional_products = all_optional_products.filtered(
            lambda p: p.product_tmpl_id.trazet_product_key not in existing_trazet_keys
        )

        # Log what was filtered (optional but helpful)
        if existing_trazet_keys:
            _logger.info(
                f"Subscription {self.name}: Excluded from optional products: "
                f"{', '.join(existing_trazet_keys)} (already in subscription)"
            )

        if not optional_products:
            return

        # The block must sort *below* every existing line: sale.order.line
        # _compute_parent_id assigns parenthood by sequence order, so a section
        # landing above real lines turns those lines into optional ones and
        # silently removes them from the totals and from invoicing.
        base_sequence = max(self.order_line.mapped('sequence'), default=0) + 100
        section_vals = {
            'order_id': self.id,
            'display_type': 'line_section',
            'is_optional': True,
            'name': _("Optional Products"),
            'sequence': base_sequence,
        }

        option_lines_vals = []
        for index, p in enumerate(optional_products, start=1):
            pricing_rules = self.plan_id.subscription_rule_ids if self.plan_id else self.env[
                'product.pricelist.item']

            matched_pricing = pricing_rules.filtered(lambda pr: (
                    pr.product_tmpl_id == p.product_tmpl_id or
                    pr.product_id == p
            ))

            price = matched_pricing[0].fixed_price if matched_pricing else p.lst_price

            option_lines_vals.append({
                'order_id': self.id,
                'product_id': p.id,
                'name': p.name,
                'price_unit': price,
                'product_uom_qty': 0,
                'product_uom_id': p.uom_id.id,
                'sequence': base_sequence + index,
            })

        self.env['sale.order.line'].with_context(
            skip_optional_products=True,
        ).create([section_vals] + option_lines_vals)

    def prepare_decrease_order(self):
        """Create a new quantity decrease order from subscription"""
        self.ensure_one()
        if not self.is_subscription or self.subscription_state not in ['3_progress', '4_paused']:
            return False

        # Similar to upsell but for decreasing quantities
        decrease_msg_body = _("A quantity decrease has been created by %s", self.env.user.name)
        action = self._prepare_renew_upsell_order('7_upsell', decrease_msg_body)

        if action and action.get('res_id'):
            # Mark the new order as a quantity decrease
            decrease_order = self.browse(action.get('res_id'))
            decrease_order.sudo().write({'is_quantity_decrease': True})

        return action

    def _confirm_quantity_decrease(self, decrease_lines):
        """
        Process quantity decrease when confirmed
        :param decrease_lines: Dictionary with line_id as key and new_qty as value
        """
        self.ensure_one()
        if not decrease_lines or not self.is_subscription:
            return False

        # First, check for any outstanding draft invoices that might be affected
        draft_invoices = self.invoice_ids.filtered(lambda inv: inv.state == 'draft')
        for invoice in draft_invoices:
            # It's safer to cancel existing draft invoices to avoid reconciliation issues
            invoice.button_cancel()
            self.message_post(body=_("Cancelled draft invoice %s as part of quantity decrease process", invoice.name))

        changes_made = False

        # Get all lines that need processing
        lines_to_process = {}
        linked_items = {}

        # First, identify main combo products and their linked items
        for line_id_str, new_qty in decrease_lines.items():
            try:
                line_id = int(line_id_str)
                line = self.env['sale.order.line'].sudo().browse(line_id)
                if not line or line.order_id != self:
                    continue

                # Store the main line for processing
                lines_to_process[line_id] = {
                    'line': line,
                    'new_qty': float(new_qty),
                    'is_combo_main': line.product_id.type == 'combo',
                }

                # If this is a combo product, find all its linked items
                if line.product_id.type == 'combo':
                    # Find all linked combo items for this main line
                    combo_items = self.order_line.filtered(
                        lambda l: l.linked_line_id and l.linked_line_id.id == line_id
                    )

                    # Store info about these linked items
                    for item in combo_items:
                        linked_items[item.id] = {
                            'line': item,
                            'main_line_id': line_id,
                            'ratio': item.product_uom_qty / line.product_uom_qty if line.product_uom_qty else 1.0
                        }
            except Exception as e:
                self.message_post(body=_("Error processing line %s: %s", line_id_str, str(e)))
                continue

        # Now process the lines
        for line_id, line_info in lines_to_process.items():
            line = line_info['line']
            new_qty = line_info['new_qty']
            old_qty = line.product_uom_qty

            # Never delete the line on decrease - keep it and set the quantity
            # (a reduction to 0 keeps the line at qty 0 so it stays visible and can
            # be increased again later). Clamp negatives to 0.
            if new_qty < 0:
                new_qty = 0

            if new_qty < old_qty:
                # Decrease quantity for this line
                line.product_uom_qty = new_qty

                # Update the recurring price calculations
                if line.recurring_invoice:
                    line.sudo()._compute_recurring_monthly()

                # If this is a combo product, update quantities of all linked items
                if line_info.get('is_combo_main'):
                    combo_items = [item_info for item_id, item_info in linked_items.items()
                                   if item_info['main_line_id'] == line_id]

                    for item_info in combo_items:
                        item_line = item_info['line']
                        # Calculate new quantity based on ratio (0 stays 0)
                        item_new_qty = new_qty * item_info['ratio']
                        item_line.product_uom_qty = item_new_qty

                        # Update recurring calculations if needed
                        if item_line.recurring_invoice:
                            item_line.sudo()._compute_recurring_monthly()

                changes_made = True
                self.message_post(body=_("Quantity for product '%s' decreased from %s to %s",
                                         line.product_id.name, old_qty, new_qty))

        # Recalculate MRR
        if changes_made:
            self.sudo()._compute_recurring_monthly()
            self.sudo()._compute_recurring_total()

            # Reset invoice-related fields to ensure correct tracking for next cycle
            order_lines = self.order_line.filtered(lambda l: l.recurring_invoice)
            order_lines.sudo()._reset_subscription_qty_to_invoice()

            self.payment_exception = False

            effective_date = self.next_invoice_date or fields.Date.today()
            self.message_post(body=_(
                "Product quantities have been updated. New MRR: %s %s. Changes will be applied from next invoice date (%s).",
                round(self.recurring_monthly, 2),
                self.currency_id.name,
                effective_date))
            return True
        return False

    def _cleanup_optional_products_on_confirm(self):
        self.ensure_one()

        section = self._get_optional_products_section()
        if not section:
            return

        optional_lines = self.order_line.filtered(lambda l: l.parent_id == section)
        if not optional_lines:
            return

        # Get only allowExternalAPI and collectPeriod that exist elsewhere in order_line with qty > 0
        # (excluding the optional placeholder lines themselves, whose qty the customer may have
        # just raised above 0 - that IS how a product gets added now).
        existing_per_sub_products = self.order_line.filtered(
            lambda l: l.recurring_invoice
                      and l.product_id.trazet_product_key in ['allowExternalAPI', 'collectPeriod']
                      and l.product_uom_qty > 0
                      and l not in optional_lines
        ).mapped('product_id')

        if not existing_per_sub_products:
            return

        # Remove only these two products from optional products
        lines_to_remove = optional_lines.filtered(
            lambda l: l.product_id in existing_per_sub_products
        )

        if lines_to_remove:
            _logger.info(
                f"Order {self.name}: Removing from optional products: {', '.join(lines_to_remove.mapped('product_id.name'))}")
            lines_to_remove.unlink()

    def action_confirm(self):
        for order in self:
            order._cleanup_optional_products_on_confirm()
        return super().action_confirm()
