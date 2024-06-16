# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class SaleOrderRecurring(models.Model):
    _name = 'sale.order.recurring'
    _inherit = 'sale.order.option'
    _description = "Sale Recurring"
    _order = 'sequence, id'

    tax_ids = fields.Many2many(
        'account.tax',
        string='Taxes')
    price_subtotal = fields.Monetary(
        string="Subtotal",
        compute='_compute_amount',
        store=True, precompute=True)
    price_tax = fields.Float(
        string="Total Tax",
        compute='_compute_amount',
        store=True, precompute=True)
    price_total = fields.Monetary(
        string="Total",
        compute='_compute_amount',
        store=True, precompute=True)
    currency_id = fields.Many2one(
        'res.currency',
        readonly=True,
        default=lambda x: x.env.company.currency_id
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """
        @private - update taxes when changing the product
        """
        if self.product_id:
            self.update({
                'tax_ids': [(4, x.id) for x in self.product_id.taxes_id]
            })

    def _convert_to_tax_base_line_dict(self, **kwargs):
        """ Convert the current record to a dictionary in order to use the generic taxes computation method
        defined on account.tax.

        :return: A python dictionary.
        """
        self.ensure_one()
        return self.env['account.tax']._convert_to_tax_base_line_dict(
            self,
            partner=self.order_id.partner_id,
            currency=self.order_id.currency_id,
            product=self.product_id,
            taxes=self.tax_ids,
            price_unit=self.price_unit,
            quantity=self.quantity,
            discount=self.discount,
            price_subtotal=self.price_subtotal,
            **kwargs,
        )

    @api.depends('quantity', 'discount', 'price_unit', 'tax_ids')
    def _compute_amount(self):
        """
        @private - Compute the amounts of the SO line.
        """
        for line in self:
            tax_results = self.env['account.tax']._compute_taxes([
                line._convert_to_tax_base_line_dict()
            ])
            totals = list(tax_results['totals'].values())[0]
            amount_untaxed = totals['amount_untaxed']
            amount_tax = totals['amount_tax']

            line.update({
                'price_subtotal': amount_untaxed,
                'price_tax': amount_tax,
                'price_total': amount_untaxed + amount_tax,
            })
