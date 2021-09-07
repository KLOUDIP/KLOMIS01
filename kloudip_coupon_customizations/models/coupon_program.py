# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class CouponProgram(models.Model):
    _inherit = 'coupon.program'

    allow_redeem_multiple_coupons = fields.Boolean(string='Allow Redeem Multiple Coupons',
                                                   help='Enabling this option will allow user to redeem multiple coupons in sale order')