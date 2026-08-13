# -*- coding: utf-8 -*-
###############################################################################
#
#    Fortutech IMS Pvt. Ltd.
#    Copyright (C) 2016-TODAY Fortutech IMS Pvt. Ltd.(<http://www.fortutechims.com>).
#
###############################################################################
from odoo import models, fields, api, _
from odoo.tools import float_compare


class SaleOrder(models.Model):
    _inherit = "sale.order"
    
    def get_parameter_value(self):
        
        res_confirm_order = self.env['ir.config_parameter'].sudo().get_param('fims_sale_automatic_workflow.web_order_conf')
        res = {}
        if res_confirm_order == 'conf_quo':
            res.update({'1':'conf_quo'})
            return 'conf_quo'
            
        if res_confirm_order == 'conf_quo_and_inv':
            res.update({'2':'conf_quo_and_inv'})
            return 'conf_quo_and_inv'
            
        if res_confirm_order == 'conf_quo_and_validate_inv':
            res.update({'3':'conf_quo_and_validate_inv'})
            return 'conf_quo_and_validate_inv'
                
        if res_confirm_order == 'conf_quo_inv_payment':
            res.update({'4':'conf_quo_inv_payment'})
            return 'conf_quo_inv_payment'
