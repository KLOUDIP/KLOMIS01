# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class SaleLoyaltyCouponWizard(models.TransientModel):
    _inherit = 'sale.loyalty.coupon.wizard'

    coupon_id = fields.Many2one('loyalty.card', string='Coupon')
    partner_id = fields.Many2one('res.partner', string='Partner')

    @api.onchange('coupon_id')
    def onchange_coupon_id(self):
        self.update({'coupon_code': self.coupon_id.code})
