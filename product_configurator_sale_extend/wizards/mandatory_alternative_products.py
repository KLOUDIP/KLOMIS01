# -*- coding: utf-8 -*-

from lxml import etree

from odoo import models, fields, tools, api, _
from odoo.exceptions import UserError


class MandatoryAlternativeProductsWizard(models.TransientModel):
    _name = "mandatory.alternative.products"
    _description = 'Mandatory Alternative Products'

    mandatory_products = fields.One2many('mandatory.alternative.products.select', 'mandatory_alternative_products_id', string='Mandatory Products', domain=[('type', '=', 'mandatory')])
    alternative_products = fields.One2many('mandatory.alternative.products.select', 'mandatory_alternative_products_id', string='Alternative Products',
                                           context={'default_type': 'alternative'}, domain=[('type', '=', 'alternative')])
    mandatory_product_ids = fields.Many2many('product.product', 'mandatory_products', compute='_compute_mandatory_products', string='Mandatory Products')
    alternative_product_ids = fields.Many2many('product.product', 'alternative_products', compute='_compute_alternative_products', string='Alternative Products')
    mandatory_products_available = fields.Boolean('Mandatory Products Available', compute='_check_products_availability')
    alternative_products_available = fields.Boolean('Alternative Products Available', compute='_check_products_availability')

    @api.depends('mandatory_products.product_id')
    def _compute_mandatory_products(self):
        """Update field value - For domain purposes"""
        products = False
        if 'mandatory_products' in self.env.context:
            products = self.env['product.product'].browse(self.env.context['mandatory_products']).filtered(lambda x: x.id not in self.mapped('mandatory_products').product_id.ids)
        for rec in self:
            rec['mandatory_product_ids'] = products

    @api.depends('alternative_products.product_id')
    def _compute_alternative_products(self):
        """Update field value - For domain purposes"""
        products = False
        if 'alternative_products' in self.env.context:
            products = self.env['product.product'].browse(self.env.context['alternative_products']).filtered(lambda x: x.id not in self.mapped('alternative_products').product_id.ids)
        for rec in self:
            rec['alternative_product_ids'] = products

    def _check_products_availability(self):
        if 'state_list' in self.env.context:
            self.update({
                'mandatory_products_available': True if 'mandatory' in self.env.context['state_list'] else False,
                'alternative_products_available': True if 'alternative' in self.env.context['state_list'] else False
            })

    def action_confirm(self):
        """Extend action confirm with previously passed context values"""
        missing_products = False
        if 'mandatory_products' in self.env.context:
            missing_products = list(set(self.env.context['mandatory_products']) - set(self.mandatory_products.mapped('product_id').ids))
        if missing_products:
            raise UserError(_('You need to add all Mandatory Products for proceed.'))
        else:
            line_values = []
            main_product_values = self.env.context.get('main_product_values')
            order_id = self.env['sale.order'].browse(self.env.context.get('sale_order_id'))
            order_line_id = self.env['sale.order.line'].browse(self.env.context.get('sale_order_line'))
            # write main product line to the sale order
            if order_line_id:
                # order_id.order_line.write(main_product_values)
                order_line_id.write(main_product_values)
            else:
                if main_product_values:
                    order_id.write({"order_line": [(0, 0, main_product_values)]})
            # update sub products to the sale order line
            for value in self.env['mandatory.alternative.products.select'].search([('mandatory_alternative_products_id', '=', self.id)]):
                line_values.append((0, 0,
                                    {'product_id': value.product_id.id,
                                     'product_uom_qty': value.quantity,
                                     'config_session_id': main_product_values['config_session_id'] if main_product_values else self.env.context['session_id']
                                     }))
            order_id.update({"order_line": line_values})
        return {'type': 'ir.actions.act_window_close'}


class MandatoryAlternativeProductsSelect(models.TransientModel):
    _name = "mandatory.alternative.products.select"
    _description = 'Mandatory Alternative Products Select'

    product_id = fields.Many2one('product.product', string='Product', required=True)
    quantity = fields.Integer(string='Quantity', required=True, default=1)
    mandatory_alternative_products_id = fields.Many2one('mandatory.alternative.products', string='Mandatory Alternative Products')
    type = fields.Selection([('mandatory', 'Mandatory'), ('alternative', 'Alternative')], string='Type')
