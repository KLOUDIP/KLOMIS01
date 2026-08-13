# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrderTemplateRecurring(models.Model):
    """Recurring (subscription) product line on a quotation template.

    ``sale.order.template.option`` was removed in Odoo 19, so the fields
    previously obtained through prototype inheritance are declared here.
    """

    _name = 'sale.order.template.recurring'
    _description = "Quotation Template Recurring Product"
    _order = 'sale_order_template_id, sequence, id'
    _check_company_auto = True

    sale_order_template_id = fields.Many2one(
        comodel_name='sale.order.template',
        string="Quotation Template Reference",
        index=True, required=True,
        ondelete='cascade')
    company_id = fields.Many2one(
        related='sale_order_template_id.company_id', store=True, index=True)
    sequence = fields.Integer(
        string="Sequence",
        help="Gives the sequence order when displaying a list of recurring products.",
        default=10)

    product_id = fields.Many2one(
        comodel_name='product.product',
        required=True, check_company=True,
        domain=lambda self: self._product_id_domain())
    name = fields.Text(
        string="Description",
        compute='_compute_name',
        store=True, readonly=False, precompute=True,
        required=True, translate=True)

    quantity = fields.Float(
        string="Quantity",
        required=True,
        digits='Product Unit',
        default=1)
    allowed_uom_ids = fields.Many2many(
        comodel_name='uom.uom', compute='_compute_allowed_uom_ids')
    uom_id = fields.Many2one(
        comodel_name='uom.uom',
        string="Unit of Measure",
        compute='_compute_uom_id',
        store=True, readonly=False,
        required=True, precompute=True,
        domain="[('id', 'in', allowed_uom_ids)]")

    #=== COMPUTE METHODS ===#

    @api.depends('product_id')
    def _compute_name(self):
        for recurring in self:
            if not recurring.product_id:
                continue
            recurring.name = recurring.product_id.get_product_multiline_description_sale()

    @api.depends('product_id')
    def _compute_allowed_uom_ids(self):
        for recurring in self:
            recurring.allowed_uom_ids = (
                recurring.product_id.uom_id | recurring.product_id.uom_ids
            )

    @api.depends('product_id')
    def _compute_uom_id(self):
        for recurring in self:
            recurring.uom_id = recurring.product_id.uom_id

    #=== BUSINESS METHODS ===#

    @api.model
    def _product_id_domain(self):
        """Returns the domain of the products that can be added as a template recurring product."""
        return [('sale_ok', '=', True)]

    def _prepare_recurring_line_values(self):
        """Give the values to create the corresponding sale order recurring line.

        :return: `sale.order.recurring` create values
        :rtype: dict
        """
        self.ensure_one()
        return {
            'name': self.name,
            'product_id': self.product_id.id,
            'quantity': self.quantity,
            'uom_id': self.uom_id.id,
        }
