# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrderTemplate(models.Model):
    _inherit = "sale.order.template"

    sale_order_template_recurring_ids = fields.One2many(
        comodel_name='sale.order.template.recurring',
        inverse_name='sale_order_template_id',
        string="Recurring Products",
        copy=True
    )
