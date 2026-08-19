# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_combo_item_display_price(self):
        self.ensure_one()

        combo_line = self._get_linked_line()
        combo_qty = combo_line.product_uom_qty
        product_quantity = self.combo_item_id.product_quantity
        self.product_uom_qty = product_quantity * combo_qty

        recurring_plan = self.order_id.plan_id if self.order_id.has_recurring_line else False
        order_currency = self.currency_id
        order_date = self.order_id.date_order
        company = self.company_id

        recurring_combo_price = False
        if recurring_plan and order_currency:
            # Simple currency-based pricing
            recurring_combo_price = self.env['combo.item.recurring.price'].get_price_for_currency(
                combo_item=self.combo_item_id,
                plan=recurring_plan,
                order_currency=order_currency,
                date=order_date,
                company=company
            )

        if recurring_combo_price:
            return recurring_combo_price + self.combo_item_id.extra_price + \
                self.product_id._get_no_variant_attributes_price_extra(
                    self.product_no_variant_attribute_value_ids
                )

        # Fallback to regular combo price with currency conversion
        if self.combo_item_id.combo_price:
            stored_currency = self.combo_item_id.currency_id
            combo_price = self.combo_item_id.combo_price

            # Convert only if currencies differ
            if stored_currency != order_currency:
                combo_price = stored_currency._convert(
                    from_amount=combo_price,
                    to_currency=order_currency,
                    company=company,
                    date=order_date or fields.Date.context_today(self)
                )

            return combo_price + self.combo_item_id.extra_price + \
                self.product_id._get_no_variant_attributes_price_extra(
                    self.product_no_variant_attribute_value_ids
                )

        # Continue with existing base price calculation logic...
        combo_product_price = combo_line._get_display_price_ignore_combo()
        combo_base_prices = {
            combo_id: combo_id.currency_id._convert(
                from_amount=combo_id.base_price,
                to_currency=order_currency,
                company=company,
                date=order_date,
            ) for combo_id in combo_line.product_template_id.combo_ids
        }
        total_combo_base_price = sum(combo_base_prices.values())
        combo_prices = {
            combo_id: order_currency.round(
                base_price * combo_product_price / (total_combo_base_price or 1)
            )
            for (combo_id, base_price) in combo_base_prices.items()
        }
        combo_price_delta = combo_product_price - sum(combo_prices.values())
        if combo_price_delta:
            combo_prices[combo_line.product_template_id.combo_ids[-1]] += combo_price_delta

        return (
                combo_prices[self.combo_item_id.combo_id]
                + self.combo_item_id.extra_price
                + self.product_id._get_no_variant_attributes_price_extra(
            self.product_no_variant_attribute_value_ids
        )
        )

    def _prepare_invoice_line(self, **optional_values):
        self.ensure_one()
        res = super()._prepare_invoice_line(**optional_values)

        if self.combo_item_id:
            res['combo_item_id'] = self.combo_item_id.id

        return res

    def _prepare_base_line_for_taxes_computation(self, **kwargs):
        self.ensure_one()
        # Custom quantity if combo item is set
        quantity = kwargs.get('quantity')
        if self.combo_item_id:
            quantity = (
                self.product_uom_qty / self.combo_item_id.product_quantity
                if self.combo_item_id.product_quantity else 1.0
            )
            kwargs['quantity'] = quantity

        return self.env['account.tax']._prepare_base_line_for_taxes_computation(
            self,
            **{
                'tax_ids': self.tax_ids,
                'quantity': quantity or self.product_uom_qty,
                'partner_id': self.order_id.partner_id,
                'currency_id': self.order_id.currency_id or self.order_id.company_id.currency_id,
                'rate': self.order_id.currency_rate,
                **kwargs,
            }
        )

    def _get_renew_upsell_values(self, subscription_state):
        order_lines = []
        description_needed, description_name = [], ""
        combo_product_lines = self.env['sale.order.line']
        combo_linked_lines = self.env['sale.order.line']
        if subscription_state == '7_upsell':
            description_needed, description_name = self._get_renew_discount_info()

            combo_product_lines = self.filtered(lambda l: l.product_id.type == 'combo')
            # Only the lines actually linked to *this* combo line belong to it. Matching by
            # product_id alone would also catch unrelated lines that happen to reference the
            # same product (e.g. that product also listed as a standalone optional product).
            combo_linked_lines = self.filtered(lambda l: l.linked_line_id in combo_product_lines)

        for line in self:
            if line.display_type == 'line_section':
                # Optional-product sections (is_optional=True) must be carried over, otherwise
                # their child lines lose the section they need to be recognized as optional
                # (`_is_line_optional`) and portal users can no longer add them from the upsell.
                if subscription_state == '7_upsell' and line.is_optional:
                    order_lines.append((0, 0, {
                        'display_type': 'line_section',
                        'is_optional': True,
                        'name': line.name,
                        'sequence': line.sequence,
                        'product_uom_qty': 0,
                    }))
                continue

            if not line.recurring_invoice:
                continue
            if subscription_state == '7_upsell' and line._is_postpaid_line():
                continue
            if subscription_state == '7_upsell' and (line in combo_product_lines or line in combo_linked_lines):
                continue

            partner_lang = line.order_id.partner_id.lang
            line = line.with_context(lang=partner_lang) if partner_lang else line
            product = line.product_id
            order_lines.append((0, 0, {
                'parent_line_id': line.id,
                'name': line.name + "(*)" if line in description_needed else line.name,
                'product_id': product.id,
                'product_uom_id': line.product_uom_id.id,
                'product_uom_qty': 0 if subscription_state == '7_upsell' else line.product_uom_qty,
                'sequence': line.sequence,
                'price_unit': line.price_unit,
                'combo_item_id': line.combo_item_id.id if line.combo_item_id else None,
                'linked_line_id': line.linked_line_id.id if line.linked_line_id else None,
            }))


        if description_needed and description_name:
            order_lines.append((0, 0,
                {
                    'display_type': 'line_note',
                    'sequence': 999,
                    'name': description_name,
                    'product_uom_qty': 0
                }
            ))

        return order_lines

