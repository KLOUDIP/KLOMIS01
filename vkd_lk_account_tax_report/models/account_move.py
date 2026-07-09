from odoo import models, fields, api
from collections import defaultdict
import json


class AccountMove(models.Model):
    _inherit = 'account.move'

    additional_info = fields.Text(string="Additional Info")

    is_sri_lankan_format = fields.Boolean(
        string='Use Sri Lankan Format',
        compute='_compute_is_sri_lankan_invoice',
        store=True
    )

    vat_18_amount = fields.Monetary(
        string="VAT 18% Amount",
        compute="_compute_vat_18_amount",
        currency_field="currency_id",
    )

    tax_breakdown = fields.Text(
        string="Tax Breakdown",
        compute="_compute_tax_breakdown",
        help="JSON string containing tax breakdown information"
    )

    available_payment_method_ids = fields.Many2many(
        comodel_name='account.payment.method',
        compute='_compute_available_payment_method_ids',
    )

    payment_method_id = fields.Many2one(
        comodel_name='account.payment.method',
        string='Payment Method',
        domain="[('id', 'in', available_payment_method_ids)]",
    )

    @api.depends('company_id')
    def _compute_available_payment_method_ids(self):
        methods = self.env['account.payment.method'].search([])
        unique = self.env['account.payment.method']
        seen = set()
        for method in methods:
            if method.name not in seen:
                seen.add(method.name)
                unique |= method

        for move in self:
            move.available_payment_method_ids = unique

    @api.depends('journal_id.is_sri_lankan_taxable')
    def _compute_is_sri_lankan_invoice(self):
        for move in self:
            move.is_sri_lankan_format = move.journal_id.is_sri_lankan_taxable

    @api.depends('invoice_line_ids.tax_ids', 'invoice_line_ids.price_unit', 'invoice_line_ids.quantity',
                 'invoice_line_ids.discount', 'currency_id')
    def _compute_vat_18_amount(self):
        for move in self:
            total_vat_18 = 0.0
            for line in move.invoice_line_ids:
                if not line.tax_ids:
                    continue

                price_after_discount = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                tax_results = line.tax_ids.compute_all(
                    price_after_discount,
                    currency=line.currency_id,
                    quantity=line.quantity,
                    product=line.product_id,
                    partner=move.partner_id
                )

                for tax_item in tax_results['taxes']:
                    tax_record = self.env['account.tax'].browse(tax_item['id'])
                    if tax_record.amount == 18.00 and tax_record.amount_type == 'percent':
                        total_vat_18 += tax_item['amount']

            move.vat_18_amount = total_vat_18

    @api.depends('invoice_line_ids.tax_ids', 'invoice_line_ids.price_unit', 'invoice_line_ids.quantity',
                 'invoice_line_ids.discount', 'currency_id')
    def _compute_tax_breakdown(self):
        for move in self:
            tax_summary = defaultdict(float)
            for line in move.invoice_line_ids:
                if not line.tax_ids:
                    continue

                price_after_discount = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                tax_results = line.tax_ids.compute_all(
                    price_after_discount,
                    currency=line.currency_id,
                    quantity=line.quantity,
                    product=line.product_id,
                    partner=move.partner_id
                )

                for tax_item in tax_results['taxes']:
                    tax_record = self.env['account.tax'].browse(tax_item['id'])
                    tax_key = f"{tax_record.name} ({tax_record.amount:.2f}%)"
                    tax_summary[tax_key] += tax_item['amount']

            breakdown_list = []
            for name, amount in tax_summary.items():
                formatted_amount = move.currency_id.round(amount)
                breakdown_list.append({
                    'name': name,
                    'amount': amount,
                    'formatted_amount': move.currency_id.format(formatted_amount)
                })

            breakdown_list.sort(key=lambda x: x['name'])
            move.tax_breakdown = json.dumps(breakdown_list)

    def get_tax_breakdown_list(self):
        if self.tax_breakdown:
            return json.loads(self.tax_breakdown)
        return []

    def format_currency_amount(self, amount):
        return self.currency_id.format(self.currency_id.round(amount))
