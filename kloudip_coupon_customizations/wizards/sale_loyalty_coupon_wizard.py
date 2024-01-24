# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class SaleLoyaltyCouponWizard(models.TransientModel):
    _inherit = 'sale.loyalty.coupon.wizard'

    coupon_id = fields.Many2one('loyalty.card', string='Coupon')
    partner_id = fields.Many2one('res.partner', string='Partner')
    reward_product_ids = fields.Many2many("product.product", string="Reward Product", compute="compute_reward_product")

    @api.onchange('coupon_id')
    def onchange_coupon_id(self):
        self.update({'coupon_code': self.coupon_id.code})

    @api.depends('coupon_id')
    def compute_reward_product(self):
        reward = self.env['loyalty.reward']
        for rec in self:
            reward = reward.search([('discount_product_ids', 'in', rec.order_id.order_line.product_id.ids)])
            line = reward.discount_line_product_id.filtered(lambda x: x.lst_price in rec.order_id.order_line.mapped('price_unit'))
            if line:
                rec.reward_product_ids = [(6, 0, line.discount_line_product_id.ids)]
            else:
                rec.reward_product_ids = False
