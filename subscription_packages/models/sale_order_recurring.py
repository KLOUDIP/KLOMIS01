# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError


class SaleOrderRecurring(models.Model):
    """Recurring (subscription) product line on a sale order.

    Until Odoo 18 this model was built by prototype inheritance on
    ``sale.order.option``. That model was removed in Odoo 19 (optional
    products became the ``is_optional`` flag on ``sale.order.line``), so the
    fields and business methods are declared explicitly here.
    """

    _name = 'sale.order.recurring'
    _description = "Sale Order Recurring Product"
    _order = 'sequence, id'
    _check_company_auto = True

    order_id = fields.Many2one(
        comodel_name='sale.order',
        string="Sales Order Reference",
        ondelete='cascade', index=True)
    company_id = fields.Many2one(
        related='order_id.company_id', store=True, index=True)
    line_id = fields.Many2one(
        comodel_name='sale.order.line', ondelete='set null', copy=False)
    sequence = fields.Integer(
        string="Sequence",
        help="Gives the sequence order when displaying a list of recurring products.")

    product_id = fields.Many2one(
        comodel_name='product.product',
        required=True,
        domain=lambda self: self._product_id_domain())
    name = fields.Text(
        string="Description",
        compute='_compute_name',
        store=True, readonly=False,
        required=True, precompute=True)

    quantity = fields.Float(
        string="Quantity",
        required=True,
        digits='Product Unit',
        default=1)
    # Odoo 19 dropped UoM categories: the allowed units are now the product's
    # reference unit plus its packagings.
    allowed_uom_ids = fields.Many2many(
        comodel_name='uom.uom', compute='_compute_allowed_uom_ids')
    uom_id = fields.Many2one(
        comodel_name='uom.uom',
        string="Unit of Measure",
        compute='_compute_uom_id',
        store=True, readonly=False,
        required=True, precompute=True,
        domain="[('id', 'in', allowed_uom_ids)]")

    price_unit = fields.Float(
        string="Unit Price",
        min_display_digits='Product Price',
        compute='_compute_price_unit',
        store=True, readonly=False,
        required=True, precompute=True)
    discount = fields.Float(
        string="Discount (%)",
        digits='Discount',
        compute='_compute_discount',
        store=True, readonly=False, precompute=True)
    tax_ids = fields.Many2many(
        comodel_name='account.tax',
        string="Taxes",
        compute='_compute_tax_ids',
        store=True, readonly=False, precompute=True,
        context={'active_test': False},
        check_company=True)

    currency_id = fields.Many2one(
        comodel_name='res.currency',
        compute='_compute_currency_id',
        store=True, precompute=True)
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

    is_present = fields.Boolean(
        string="Present on Quotation",
        compute='_compute_is_present',
        search='_search_is_present',
        help="This field will be checked if the recurring line's product is "
             "already present in the quotation.")

    #=== COMPUTE METHODS ===#

    @api.depends('product_id')
    def _compute_name(self):
        for recurring in self:
            if not recurring.product_id:
                continue
            product_lang = recurring.product_id.with_context(
                lang=recurring.order_id.partner_id.lang)
            recurring.name = product_lang.get_product_multiline_description_sale()

    @api.depends('product_id')
    def _compute_allowed_uom_ids(self):
        for recurring in self:
            recurring.allowed_uom_ids = (
                recurring.product_id.uom_id | recurring.product_id.uom_ids
            )

    @api.depends('product_id')
    def _compute_uom_id(self):
        for recurring in self:
            if not recurring.product_id or recurring.uom_id:
                continue
            recurring.uom_id = recurring.product_id.uom_id

    @api.depends('order_id.currency_id', 'company_id')
    def _compute_currency_id(self):
        for recurring in self:
            recurring.currency_id = (
                recurring.order_id.currency_id
                or recurring.company_id.currency_id
                or recurring.env.company.currency_id
            )

    def _discard_pricing_line(self, new_sol):
        """Detach *and forget* the in-cache sale.order.line used only for pricing.

        Setting ``order_id = False`` is not enough: the record stays queued in
        ``env.transaction.tocompute`` for the stored computed fields of
        sale.order.line (price_subtotal/price_total/price_tax).
        ``Field.recompute()`` batches all pending ids together via
        ``expand_ids()``, so the next read of ``price_subtotal`` on a *real*
        order line drags this order-less line into the same ``_compute_amount``
        call - where it has no currency and the tax engine asserts on
        ``precision_rounding == 0.0``.

        Dropping it from ``tocompute`` is enough and is the only safe thing to
        do here. Do NOT call ``invalidate_recordset()`` on the throw-away line:
        that also invalidates the *inverse* of every relational field with
        ``ids=None``, which wipes ``sale.order.order_line`` out of the cache for
        every order in the transaction - including the one the onchange is
        currently building, whose lines would then silently disappear.
        """
        env = new_sol.env
        # Unset first: writing order_id re-marks the dependent stored computes,
        # so the tocompute cleanup below has to come after it.
        new_sol.order_id = False
        for field in new_sol._fields.values():
            if field.store and field.compute:
                env.remove_to_compute(field, new_sol)

    @api.depends('product_id', 'uom_id', 'quantity')
    def _compute_price_unit(self):
        for recurring in self:
            if not recurring.product_id:
                continue
            # To compute the price_unit a so line is created in cache
            new_sol = self.env['sale.order.line'].new(
                recurring._get_values_to_add_to_order())
            new_sol._compute_price_unit()
            recurring.price_unit = new_sol.price_unit
            recurring._discard_pricing_line(new_sol)

    @api.depends('product_id', 'uom_id', 'quantity')
    def _compute_discount(self):
        for recurring in self:
            if not recurring.product_id:
                continue
            # To compute the discount a so line is created in cache
            new_sol = self.env['sale.order.line'].new(
                recurring._get_values_to_add_to_order())
            new_sol._compute_discount()
            recurring.discount = new_sol.discount
            recurring._discard_pricing_line(new_sol)

    @api.depends('product_id', 'company_id', 'order_id.fiscal_position_id')
    def _compute_tax_ids(self):
        for recurring in self:
            company = recurring.company_id or recurring.env.company
            if not recurring.product_id:
                recurring.tax_ids = False
                continue
            taxes = recurring.product_id.taxes_id._filter_taxes_by_company(company)
            recurring.tax_ids = recurring.order_id.fiscal_position_id.map_tax(taxes)

    @api.depends('quantity', 'discount', 'price_unit', 'tax_ids', 'currency_id')
    def _compute_amount(self):
        AccountTax = self.env['account.tax']
        for recurring in self:
            company = recurring.company_id or recurring.env.company
            base_line = recurring._prepare_base_line_for_taxes_computation()
            AccountTax._add_tax_details_in_base_line(base_line, company)
            AccountTax._round_base_lines_tax_details([base_line], company)
            recurring.price_subtotal = base_line['tax_details']['total_excluded_currency']
            recurring.price_total = base_line['tax_details']['total_included_currency']
            recurring.price_tax = recurring.price_total - recurring.price_subtotal

    @api.depends('line_id', 'order_id.order_line', 'product_id')
    def _compute_is_present(self):
        # NOTE: this field cannot be stored as the line_id is usually removed
        # through cascade deletion, which means the compute would be false
        for recurring in self:
            recurring.is_present = bool(recurring.order_id.order_line.filtered(
                lambda line: line.product_id == recurring.product_id))

    def _search_is_present(self, operator, value):
        # Odoo 19 normalises boolean searches to the 'in' / 'not in' operators.
        if operator != 'in':
            return NotImplemented
        if list(value) == [True]:
            return [('line_id', '=', False)]
        return [('line_id', '!=', False)]

    #=== BUSINESS METHODS ===#

    @api.model
    def _product_id_domain(self):
        """Returns the domain of the products that can be added as a recurring product."""
        return [('sale_ok', '=', True)]

    def _prepare_base_line_for_taxes_computation(self, **kwargs):
        """Convert the current record into the dict expected by the generic
        taxes computation helpers defined on ``account.tax``.

        Replaces the pre-18 ``_convert_to_tax_base_line_dict``.

        :return: A python dictionary.
        """
        self.ensure_one()
        company = self.company_id or self.env.company
        return self.env['account.tax']._prepare_base_line_for_taxes_computation(
            self,
            tax_ids=self.tax_ids,
            quantity=self.quantity,
            product_uom_id=self.uom_id,
            partner_id=self.order_id.partner_id,
            currency_id=self.currency_id or self.order_id.currency_id or company.currency_id,
            rate=self.order_id.currency_rate or 1.0,
            name=self.name,
            **kwargs,
        )

    def _get_inside_product_documents(self):
        """Product documents meant to be merged inside the quotation PDF for
        the products of these recurring lines.

        ``attached_on`` was renamed ``attached_on_sale`` in Odoo 18 and is
        restricted to salespeople, hence the sudo.
        """
        if not self:
            return self.env['product.document']
        return self.env['product.document'].sudo().search(
            [
                ('attached_on_sale', '=', 'inside'),
                '|',
                    '&',
                        ('res_model', '=', 'product.product'),
                        ('res_id', 'in', self.product_id.ids),
                    '&',
                        ('res_model', '=', 'product.template'),
                        ('res_id', 'in', self.product_id.product_tmpl_id.ids),
            ],
            order='res_model, sequence',
        )

    def _get_values_to_add_to_order(self):
        self.ensure_one()
        return {
            'order_id': self.order_id.id,
            'price_unit': self.price_unit,
            'technical_price_unit': self.price_unit,
            'name': self.name,
            'product_id': self.product_id.id,
            'product_uom_qty': self.quantity,
            'product_uom_id': self.uom_id.id,
            'discount': self.discount,
            'sequence': max(self.order_id.order_line.mapped('sequence'), default=0) + 1,
        }

    #=== ACTION METHODS ===#

    def button_add_to_order(self):
        self.add_recurring_to_order()

    def add_recurring_to_order(self):
        self.ensure_one()

        if not self.order_id._can_be_edited_on_portal():
            raise UserError(self.env._("You cannot add products to a confirmed order."))

        order_line = self.env['sale.order.line'].create(
            self._get_values_to_add_to_order())
        self.line_id = order_line

        return order_line
