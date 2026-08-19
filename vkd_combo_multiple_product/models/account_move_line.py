from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    combo_item_id = fields.Many2one('product.combo.item', string='Combo Item')

