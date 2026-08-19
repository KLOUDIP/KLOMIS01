# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only.
from odoo import fields, models


class StockProductionLot(models.Model):
    _inherit = 'stock.lot'

    fios_lot_no = fields.Char(
        string='FIOS Serial Number',
        help='This field will fill with the FIOS Serial Number, If the system lot number '
             'number and FIOS serial number is mismatch.')
