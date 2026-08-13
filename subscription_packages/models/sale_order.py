# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    custom_plan_id = fields.Many2one(
        comodel_name='sale.subscription.plan',
        string="Subscription Plan",
        help="User selected recurring pricing on invoice preview will appear here",
        context={'sale_recurring': True},
        tracking=1,
        default=lambda self: self.env['sale.subscription.plan'].search(
            [('name', '=', 'Monthly')], limit=1),
    )
    sale_order_recurring_ids = fields.One2many(
        comodel_name='sale.order.recurring',
        inverse_name='order_id',
        string="Subscription Products Lines",
        copy=True,
    )
    sub_tax_totals = fields.Binary(compute='_compute_sub_tax_totals', exportable=False)

    #=== COMPUTE METHODS ===#

    @api.depends_context('lang')
    @api.depends(
        'sale_order_recurring_ids.price_subtotal',
        'sale_order_recurring_ids.tax_ids',
        'sale_order_recurring_ids.price_unit',
        'currency_id',
        'company_id',
    )
    def _compute_sub_tax_totals(self):
        """Totals of the subscription lines.

        Odoo 18 removed ``account.tax._prepare_tax_totals`` in favour of
        ``_get_tax_totals_summary``, fed with base line dicts.
        """
        AccountTax = self.env['account.tax']
        for order in self:
            base_lines = [
                line._prepare_base_line_for_taxes_computation()
                for line in order.sale_order_recurring_ids
            ]
            AccountTax._add_tax_details_in_base_lines(base_lines, order.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, order.company_id)
            order.sub_tax_totals = AccountTax._get_tax_totals_summary(
                base_lines=base_lines,
                currency=order.currency_id or order.company_id.currency_id,
                company=order.company_id,
            )

    #=== ONCHANGE METHODS ===#

    @api.onchange('custom_plan_id')
    def _onchange_custom_plan_id(self):
        """Update the recurring product prices from the recurring pricelist
        rules of the selected subscription plan.

        Odoo 18 removed sale.subscription.pricing; recurring prices are now
        product.pricelist.item records carrying the plan.
        """
        if not self.custom_plan_id:
            return

        PricelistItem = self.env['product.pricelist.item']
        for recurring in self.sale_order_recurring_ids:
            if not recurring.product_id:
                continue
            item = PricelistItem.search([
                ('plan_id', '=', self.custom_plan_id.id),
                ('pricelist_id', '=', self.pricelist_id.id),
                '|',
                ('product_id', '=', recurring.product_id.id),
                '&',
                ('product_id', '=', False),
                ('product_tmpl_id', '=', recurring.product_id.product_tmpl_id.id),
            ], limit=1)
            recurring.price_unit = item.fixed_price if item else 0.0

    @api.onchange('sale_order_template_id')
    def _onchange_sale_order_template_id(self):
        """Override to also load the recurring products of the template."""
        res = super()._onchange_sale_order_template_id()

        sale_order_template = self.sale_order_template_id.with_context(
            lang=self.partner_id.lang)
        recurring_lines_data = [fields.Command.clear()]
        recurring_lines_data += [
            fields.Command.create(recurring._prepare_recurring_line_values())
            for recurring in sale_order_template.sale_order_template_recurring_ids
        ]
        self.sale_order_recurring_ids = recurring_lines_data

        return res
