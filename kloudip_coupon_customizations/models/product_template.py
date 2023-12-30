# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_coupon_product = fields.Boolean('Is Coupon Product', store=True)
    coupon_program_id = fields.Many2one('loyalty.program', string='Loyalty Program',
                                        domain="[('program_type','=', 'coupons')]",
                                        help='This field will use for identify coupon program when selling this product')

    @api.onchange('is_coupon_product')
    def onchange_is_coupon_product(self):
        """Setting product saleable when Is Coupon Product enabled"""
        if self.is_coupon_product:
            self.update({
                'sale_ok': True,
                'type': 'service'
            })
        else:
            self.update({'coupon_program_id': False})
