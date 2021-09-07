# -*- encoding: utf-8 -*-

from odoo import models
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        """Override - Set sale order assigned coupon state to new, when returning the delivery"""
        if self.sale_id and self.picking_type_id.code in ['incoming'] and self.sale_id.applied_coupon_ids:
            program_id = self.sale_id.applied_coupon_ids.mapped('program_id')
            # check there are multiple programs assigned to sale order
            if len(program_id) > 1:
                raise ValidationError(_('Multiple coupon programs found for sale order'))
            else:
                coupon_program_product_lines = self.move_ids_without_package.filtered(lambda x: x.product_id.id in program_id.discount_specific_product_ids.ids)
                # check multiple product lines available with coupon product ids
                if len(coupon_program_product_lines) > 1:
                    raise ValidationError(_('Multiple coupon product lines found.'))
                elif len(coupon_program_product_lines) == 1:
                    # set coupon to valid state with checking return quantity
                    self.sale_id.applied_coupon_ids[0:int(coupon_program_product_lines.quantity_done)].update({'state': 'new', 'sales_order_id': False})

        return super(StockPicking, self).button_validate()