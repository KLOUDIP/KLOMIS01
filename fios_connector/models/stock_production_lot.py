# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _


class StockProductionLot(models.Model):
    _inherit = 'stock.lot'

    fios_lot_no = fields.Char(string='FIOS Serial Number',
                                        help='This field will fill with the FIOS Serial Number, If the system lot number number and FIOS serial number is mismatch.')