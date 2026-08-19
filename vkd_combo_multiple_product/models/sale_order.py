# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'


    def _next_billing_details(self):
        """ Prepare the dictionary of next invoice's details i.e product, tax and amount.

        :return: The values of upcoming bill.
        :rtype: dict
        """
        self.ensure_one()
        AccountTax = self.env['account.tax']

        def get_tax_totals(display_lines):
            base_lines = []

            for line in display_lines:
                if line.combo_item_id:
                    quantity = (
                        line.product_uom_qty / line.combo_item_id.product_quantity
                        if line.combo_item_id.product_quantity != 0 else 1
                    )
                    base_line = line._prepare_base_line_for_taxes_computation(
                        quantity=quantity
                    )
                else:
                    base_line = line._prepare_base_line_for_taxes_computation()

                base_lines.append(base_line)
            AccountTax._add_tax_details_in_base_lines(base_lines, self.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, self.company_id)
            return AccountTax._get_tax_totals_summary(
                base_lines=base_lines,
                currency=self.currency_id or self.company_id.currency_id,
                company=self.company_id,
            )

        display_lines = self._get_invoiceable_lines()
        amount_to_pay = get_tax_totals(display_lines) if display_lines else dict()

        # Considering the product having delivery policy but not deliver
        undelivered_lines = self.order_line.filtered(lambda line: line.product_uom_qty and not line.qty_delivered and line.product_id.invoice_policy == "delivery")
        if undelivered_lines:
            display_lines += undelivered_lines
        # We always display recurring product
        if not display_lines:
            display_lines = self.order_line.filtered(lambda line: line.product_id.recurring_invoice)
        if self.subscription_state == '5_renewed':
            display_lines = self.order_line

        tax_totals = get_tax_totals(display_lines)
        return {
            'sale_order': self,
            'display_lines': display_lines,
            'next_invoice_amount': amount_to_pay.get('total_amount') or 0.0,
            'tax_totals': tax_totals
        }
