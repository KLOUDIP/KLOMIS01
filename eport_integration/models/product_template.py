# -*- coding: utf-8 -*-
import logging

from odoo import models, fields

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = "product.template"

    is_epc = fields.Boolean(string="Is a EPC")
