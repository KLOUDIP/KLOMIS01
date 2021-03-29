# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ProductProduct(models.Model):
    _inherit = "product.product"

    compulsory_product_ids = fields.Many2many(
        'product.product', 'rel_product_compulsory', 'id', 'product_id', check_company=True,
        string='Compulsory Products')
    non_compulsory_product_ids = fields.Many2many(
        'product.product', 'rel_product_non_compulsory', 'id', 'product_id', check_company=True,
        string='Non-Compulsory Products')