# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.onchange('is_coupon_product')
    def onchange_is_coupon_product(self):
        """Setting product saleable when Is Coupon Product enabled"""
        if self.product_tmpl_id and self.is_coupon_product:
            self.product_tmpl_id.onchange_is_coupon_product()
