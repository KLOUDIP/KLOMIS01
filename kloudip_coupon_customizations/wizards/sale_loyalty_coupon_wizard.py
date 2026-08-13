# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleLoyaltyCouponWizard(models.TransientModel):
    _inherit = 'sale.loyalty.coupon.wizard'

    coupon_id = fields.Many2one('loyalty.card', string='Coupon')
    partner_id = fields.Many2one('res.partner', string='Partner')
    reward_product_ids = fields.Many2many("product.product", string="Reward Product", compute="compute_reward_product")

    @api.onchange('coupon_id')
    def onchange_coupon_id(self):
        for rec in self:
            rec.coupon_code = rec.coupon_id.code

    @api.depends('coupon_id', 'order_id')
    def compute_reward_product(self):
        reward_model = self.env['loyalty.reward']
        for rec in self:
            if not rec.order_id:
                rec.reward_product_ids = self.env['product.product']
                continue

            rewards = reward_model.search([('discount_product_ids', 'in', rec.order_id.order_line.product_id.ids)])
            lines = rewards.discount_line_product_id.filtered(
                lambda x: x.lst_price in rec.order_id.order_line.mapped('price_reduce_taxexcl'))

            rec.reward_product_ids = lines if lines else self.env['product.product']
