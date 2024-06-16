# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrderTemplateRecurring(models.Model):
    _name = "sale.order.template.recurring"
    _inherit = 'sale.order.template.option'
    _description = 'Sale Order Template Recurring'
