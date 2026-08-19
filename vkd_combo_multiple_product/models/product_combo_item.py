# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ProductComboItem(models.Model):
    _inherit = 'product.combo.item'

    product_quantity = fields.Float(
        string="Quantity",
        default=1.0,
        required=True,
        help="The quantity of this product to include in the combo"
    )

    combo_price = fields.Monetary(
        string="Combo Price (Custom)",
        help="Custom combo price used if product quantity is greater than 1",
        currency_field='currency_id',
        required=True,

    )

    recurring_price_ids = fields.One2many('combo.item.recurring.price', 'combo_item_id', string='Recurring Plan Prices')

    def action_manage_recurring_prices(self):
        """
        Create pricing records for each plan + pricelist combination
        """
        self.ensure_one()

        # Find parent template
        parent_template = self.env['product.template'].search([
            ('combo_ids', 'in', [self.combo_id.id])
        ], limit=1)

        if not parent_template:
            action = self.env['ir.actions.act_window']._for_xml_id(
                'vkd_combo_multiple_product.combo_item_recurring_price_action')
            action['domain'] = [('combo_item_id', '=', self.id)]
            return action

        # Recurring pricing now lives on `product.pricelist.item` records (via `plan_id`),
        # not on the removed `sale.subscription.pricing` model.
        template_pricings = parent_template.subscription_rule_ids.filtered(
            lambda pr: pr.compute_price == 'fixed' and pr.plan_id and pr.pricelist_id
        )
        if not template_pricings:
            action = self.env['ir.actions.act_window']._for_xml_id(
                'vkd_combo_multiple_product.combo_item_recurring_price_action')
            action['domain'] = [('combo_item_id', '=', self.id)]
            return action

        # Get existing combo pricing records
        existing_records = self.recurring_price_ids
        existing_keys = set()
        for record in existing_records:
            key = (record.recurring_plan_id.id, record.pricelist_id.id)
            existing_keys.add(key)

        vals_list = []
        for pricing in template_pricings:
            pricing_key = (pricing.plan_id.id, pricing.pricelist_id.id)

            # Skip if already exists
            if pricing_key in existing_keys:
                continue

            # Create exact combination only
            vals_list.append({
                'combo_item_id': self.id,
                'recurring_plan_id': pricing.plan_id.id,
                'pricelist_id': pricing.pricelist_id.id,  # Always required now
                'combo_price': pricing.fixed_price,
                'currency_id': pricing.currency_id.id,
            })

        if vals_list:
            self.env['combo.item.recurring.price'].create(vals_list)

        action = self.env['ir.actions.act_window']._for_xml_id(
            'vkd_combo_multiple_product.combo_item_recurring_price_action')
        action['domain'] = [('combo_item_id', '=', self.id)]
        return action

    def get_combo_price_for_exact_combination(self, plan, pricelist, target_currency=None, date=None, company=None):
        """
        Get combo price for exact plan + pricelist combination only
        No fallback logic

        :param plan: sale.subscription.plan record
        :param pricelist: product.pricelist record (required)
        :param target_currency: res.currency record for conversion (optional)
        :return: Price amount or 0.0 if not found
        """
        self.ensure_one()

        if not pricelist:
            return 0.0

        # Get exact pricing - no fallback
        pricing = self.env['combo.item.recurring.price'].get_pricing_for_combo_item(
            combo_item=self,
            plan=plan,
            pricelist=pricelist
        )

        if not pricing:
            return 0.0

        # Return converted price if target currency specified
        if target_currency:
            return pricing.get_price_in_order_currency(
                order_currency=target_currency,
                date=date,
                company=company
            )
        else:
            return pricing.combo_price