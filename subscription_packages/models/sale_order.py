# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    custom_plan_id = fields.Many2one(
        'sale.subscription.plan',
        string='Subscription Plan',
        help='User selected recurring pricing on invoice preview will appear here',
        context={'sale_recurring': True},
        tracking=1,
        default=lambda self: self.env['sale.subscription.plan'].search([('name', '=', 'Monthly')], limit=1)
    )
    sale_order_recurring_ids = fields.One2many(
        comodel_name='sale.order.recurring',
        inverse_name='order_id',
        string="Subscription Products Lines",
        copy=True
    )
    sub_tax_totals = fields.Binary(compute='_compute_sub_tax_totals', exportable=False)

    @api.depends_context('lang')
    @api.depends('sale_order_recurring_ids.tax_ids', 'sale_order_recurring_ids.price_unit', 'currency_id')
    def _compute_sub_tax_totals(self):
        for order in self:
            order_lines = order.sale_order_recurring_ids
            order.sub_tax_totals = self.env['account.tax']._prepare_tax_totals(
                [x._convert_to_tax_base_line_dict() for x in order_lines],
                order.currency_id or order.company_id.currency_id,
            )

    @api.onchange('custom_plan_id')
    def _onchange_custom_plan_id(self):
        """
        @private - update recurring product price using assigned price-list in the subscription plan
        """
        if self.custom_plan_id:
            for rec in self.sale_order_recurring_ids:
                plan_line_id = self.custom_plan_id.product_subscription_pricing_ids.filtered(lambda x: x.product_template_id.id == rec.product_id.product_tmpl_id.id and x.pricelist_id.id == self.pricelist_id.id)
                price_unit = 0.00
                if plan_line_id:
                    # price_unit = plan_line_id.pricelist_id._get_product_price(rec.product_id, rec.quantity or 1.0, currency=plan_line_id[0].pricelist_id.currency_id)
                    price_unit = plan_line_id.price
                rec.update({
                    'price_unit': price_unit
                })

    @api.onchange('sale_order_template_id')
    def _onchange_sale_order_template_id(self):
        """
        @Override - Add Recurring Products Lines
        """
        res = super()._onchange_sale_order_template_id()
        sale_order_template = self.sale_order_template_id.with_context(lang=self.partner_id.lang)
        recurring_lines_data = [fields.Command.clear()]
        recurring_lines_data += [
            fields.Command.create(recurring._prepare_recurring_line_values())
            for recurring in sale_order_template.sale_order_template_recurring_ids
        ]

        self.sale_order_recurring_ids = recurring_lines_data
        return res
