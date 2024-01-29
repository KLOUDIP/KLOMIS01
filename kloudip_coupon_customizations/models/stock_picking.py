# -*- encoding: utf-8 -*-
import logging
from odoo import models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        """
            @override - Set sale order assigned coupon state to new, when returning the delivery
        """
        if self.sale_id and self.picking_type_id.code in ['incoming'] and self.sale_id.applied_coupon_ids:
            program_id = self.sale_id.applied_coupon_ids.filtered(lambda x: x.state == 'used' and x.sales_order_id == self.sale_id.id).mapped('program_id')
            # check there are multiple programs assigned to sale order
            _logger.info(program_id)
            if len(program_id) > 1:
                raise ValidationError(_('Multiple coupon programs found for sale order'))
            else:
                coupon_program_product_lines = self.move_ids_without_package.filtered(lambda x: x.product_id.id in program_id.reward_ids.discount_product_ids.ids)
                # check multiple product lines available with coupon product ids
                if len(coupon_program_product_lines) > 1:
                    raise ValidationError(_('Multiple coupon product lines found.'))
                elif len(coupon_program_product_lines) == 1:
                    # set coupon to valid state with checking return quantity
                    coupons = self.sale_id.applied_coupon_ids.filtered(lambda x: x.state == 'used' and x.sales_order_id == self.sale_id.id)
                    _logger.info(coupons)
                    if coupons:
                        coupon = coupons[0:int(coupon_program_product_lines.quantity_done)]
                        line = self.sale_id.order_line.filtered(lambda x: x.is_reward_line)
                        if line:
                            coupon.update({'state': 'new', 'sales_order_id': False, 'points': 1})

        return super(StockPicking, self).button_validate()
