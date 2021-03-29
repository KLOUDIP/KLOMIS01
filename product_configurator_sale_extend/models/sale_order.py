# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def add_missing_products(self):
        """Will open alternative mandatory products for missing products"""
        config_line = self.order_line.filtered(lambda x: x.config_ok)
        if len(config_line) == 1:
            config_product = config_line.product_id
            existing_sub_alt_products = self.order_line.filtered(lambda x: not x.config_ok and (x.product_id.id in config_product.non_compulsory_product_ids.ids)).mapped('product_id').ids
            alternative_products = [x for x in config_product.non_compulsory_product_ids.ids if x not in existing_sub_alt_products]
            if alternative_products:
                return {
                    'name': _('Select Additional Products'),
                    'view_mode': 'form',
                    'view_type': 'form',
                    'res_model': 'mandatory.alternative.products',
                    'type': 'ir.actions.act_window',
                    'target': 'new',
                    'context': {'alternative_products': alternative_products,
                                'mandatory_products': [],
                                'state_list': ['alternative'],
                                'sale_order_id': self.id,
                                'session_id': config_line.config_session_id.id,
                                'default_alternative_products_available': True}
                }
            else:
                raise ValidationError(_('No Optional Products Found for existing Configuration Product!'))
        elif len(config_line) > 0:
            raise ValidationError(_('Multiple Order Line Found with Configuration Products!'))
        else:
            raise ValidationError(_('No Order Line Found with Congfiguration Product! \nYou need to add Configuration Product before adding opional products.'))


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def reconfigure_product(self):
        """Extending Core Method - Reconfigure context added for reconfigure button"""
        wizard_model = "product.configurator.sale"

        extra_vals = {
            "order_id": self.order_id.id,
            "order_line_id": self.id,
            "product_id": self.product_id.id,
        }
        self = self.with_context(
            {
                "default_order_id": self.order_id.id,
                "default_order_line_id": self.id,
                "reconfigure": True
            }
        )
        return self.product_id.product_tmpl_id.create_config_wizard(
            model_name=wizard_model, extra_vals=extra_vals
        )