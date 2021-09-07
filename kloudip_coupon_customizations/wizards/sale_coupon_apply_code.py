# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.sale_coupon.wizard.sale_coupon_apply_code import SaleCouponApplyCode as SaleCouponApplyCodeBase


def apply_coupon(self, order, coupon_code):
    """Overload core method"""
    error_status = {}
    program = self.env['coupon.program'].search([('promo_code', '=', coupon_code)])
    if program:
        error_status = program._check_promo_code(order, coupon_code)
        if not error_status:
            if program.promo_applicability == 'on_next_order':
                # Avoid creating the coupon if it already exist
                if program.discount_line_product_id.id not in order.generated_coupon_ids.filtered(
                        lambda coupon: coupon.state in ['new', 'reserved']).mapped('discount_line_product_id').ids:
                    coupon = order._create_reward_coupon(program)
                    return {
                        'generated_coupon': {
                            'reward': coupon.program_id.discount_line_product_id.name,
                            'code': coupon.code,
                        }
                    }
            else:  # The program is applied on this order
                order._create_reward_line(program)
                order.code_promo_program_id = program
    else:
        coupon = self.env['coupon.coupon'].search([('code', '=', coupon_code)], limit=1)
        if coupon:
            error_status = coupon._check_coupon_code(order)
            if not error_status:
                # --
                coupon_program_line = order.order_line.filtered(lambda x: x.coupon_program_id)
                if len(coupon_program_line) == 1:
                    coupon_program_line.update({'product_uom_qty': coupon_program_line['product_uom_qty'] + 1})
                elif len(coupon_program_line) == 0:
                    order._create_reward_line(coupon.program_id)
                else:
                    raise ValidationError(_('Multiple coupon order lines found'))
                # --
                order.applied_coupon_ids += coupon
                coupon.write({'state': 'used'})
        else:
            error_status = {'not_found': _('This coupon is invalid (%s).') % (coupon_code)}
    return error_status


SaleCouponApplyCodeBase.apply_coupon = apply_coupon


class SaleCouponApplyCode(models.TransientModel):
    _inherit = 'sale.coupon.apply.code'

    coupon_id = fields.Many2one('coupon.coupon', string='Coupon')
    partner_id = fields.Many2one('res.partner', string='Partner')

    @api.onchange('coupon_id')
    def onchange_coupon_id(self):
        self.update({'coupon_code': self.coupon_id.code})
