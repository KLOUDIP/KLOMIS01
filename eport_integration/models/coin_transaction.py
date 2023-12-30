# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class CoinTransaction(models.Model):
    _name = "coin.transaction"
    _description = "Coin Transactions"

    name = fields.Char(string="Name")
    date = fields.Datetime(string="Date")
    amount = fields.Float(string="Amount")
    type = fields.Selection([('top_up', 'Top Up'), ('consumed', 'Consumed')], string="Type")
    state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirm'), ('cancel', 'Cancel')], string="State")
    order_id = fields.Many2one("sale.order", string="Order")
    partner_id = fields.Many2one('res.partner', string="Contact")

    @api.model_create_multi
    def create(self, values):
        for vals in values:
            if 'name' not in vals:
                vals['name'] = self.env['ir.sequence'].next_by_code('coin.transaction') or 'New'
        return super(CoinTransaction, self).create(values)

