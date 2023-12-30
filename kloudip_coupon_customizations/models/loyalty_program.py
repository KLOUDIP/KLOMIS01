# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class LoyaltyProgram(models.Model):
    _inherit = 'loyalty.program'

    allow_redeem_multiple_coupons = fields.Boolean(
        string='Allow Redeem Multiple Coupons',
        help='Enabling this option will allow user to redeem multiple coupons in sale order'
    )
