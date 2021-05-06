# -*- coding: utf-8 -*-
###############################################################################
#
#    Fortutech IMS Pvt. Ltd.
#    Copyright (C) 2016-TODAY Fortutech IMS Pvt. Ltd.(<http://www.fortutechims.com>).
#
###############################################################################
from ast import literal_eval
from odoo import api, fields, models
from odoo.exceptions import AccessDenied

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    web_order_conf = fields.Selection([
        ('conf_quo', 'Confirm Quotation'),
        ('conf_quo_and_inv', 'Confirm Quotation and Create Invoice'),
        ('conf_quo_and_validate_inv', 'Confirm Quotation and Validate Invoice'),
        ('conf_quo_inv_payment', 'Confirm Quotation, Validate Invoice and Create Payment')
        ], 'Website Order Configuration',
        default='conf_quo')

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('fims_sale_automatic_workflow.web_order_conf', self[0].web_order_conf)
        
    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        res.update(
            web_order_conf=params.get_param('fims_sale_automatic_workflow.web_order_conf', default='conf_quo'),
            )
        return res
        