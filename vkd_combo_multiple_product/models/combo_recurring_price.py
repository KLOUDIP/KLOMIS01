import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ComboItemRecurringPrice(models.Model):
    _name = 'combo.item.recurring.price'
    _description = 'Combo Price by Recurring Plan'
    _order = 'combo_item_id, recurring_plan_id, pricelist_id'

    recurring_plan_id = fields.Many2one('sale.subscription.plan', required=True)
    combo_item_id = fields.Many2one('product.combo.item', required=True, ondelete='cascade')
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', required=True, ondelete='cascade')
    combo_price = fields.Monetary('Combo Price', required=True)
    currency_id = fields.Many2one('res.currency', required=True, default=lambda self: self.env.company.currency_id)
    product_id = fields.Many2one('product.product', required=True, related='combo_item_id.product_id')
    product_quantity = fields.Float(string="Quantity", related='combo_item_id.product_quantity')
    company_id = fields.Many2one('res.company', related='recurring_plan_id.company_id')

    @api.constrains('recurring_plan_id', 'combo_item_id', 'pricelist_id')
    def _check_unique_pricing(self):
        """Ensure unique combination of plan + combo item + pricelist"""
        for record in self:
            domain = [
                ('recurring_plan_id', '=', record.recurring_plan_id.id),
                ('combo_item_id', '=', record.combo_item_id.id),
                ('pricelist_id', '=', record.pricelist_id.id),
                ('id', '!=', record.id)
            ]
            if self.search_count(domain) > 0:
                raise UserError(_(
                    "There is already a pricing for combo item '%s', plan '%s' and pricelist '%s'."
                ) % (record.combo_item_id.display_name, record.recurring_plan_id.name, record.pricelist_id.name))

    @api.model
    def get_price_for_currency(self, combo_item, plan, order_currency, date=None, company=None):
        """
        Simple currency-based pricing:
        1. Check if combo has pricelist for order currency
        2. If yes, return that price
        3. If no, find any pricing and convert to order currency

        :param combo_item: product.combo.item record
        :param plan: sale.subscription.plan record
        :param order_currency: res.currency record
        :param date: Date for conversion
        :param company: Company for conversion
        :return: Price in order currency or False
        """
        if not order_currency:
            return False

        # Step 1: Try to find pricing with pricelist that matches order currency
        currency_match_pricing = self.search([
            ('combo_item_id', '=', combo_item.id),
            ('recurring_plan_id', '=', plan.id),
            ('pricelist_id.currency_id', '=', order_currency.id)
        ], limit=1)

        if currency_match_pricing:
            # Found exact currency match - return price directly
            return currency_match_pricing.combo_price

        # Step 2: No currency match - find any pricing and convert
        any_pricing = self.search([
            ('combo_item_id', '=', combo_item.id),
            ('recurring_plan_id', '=', plan.id)
        ], limit=1)

        if any_pricing:
            # Convert from stored currency to order currency
            if not date:
                date = fields.Date.context_today(self)
            if not company:
                company = self.env.company

            converted_price = any_pricing.currency_id._convert(
                from_amount=any_pricing.combo_price,
                to_currency=order_currency,
                company=company,
                date=date
            )
            return converted_price

        return False