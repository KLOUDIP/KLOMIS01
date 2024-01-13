# -*- coding: utf-8 -*-
import uuid
import logging
import requests

from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):

    _inherit = 'res.partner'

    last_updated_epc_amount = fields.Float(string="Last Updated EPC")
    current_coin_balance = fields.Float(string="Current Coin Balance", compute="get_epc_balance")
    cumulative_coins = fields.Float(string="Cumulative Coins")
    transaction_ids = fields.One2many('coin.transaction', 'partner_id', string="Transactions")
    uuid = fields.Char(string="UUID")

    @api.depends('transaction_ids')
    def get_epc_balance(self):
        for rec in self:
            rec.current_coin_balance = sum(rec.transaction_ids.mapped('amount'))

    def create_transaction(self, transaction):
        data = {
            'date': transaction.get('date', False),
            'amount': -1 * int(transaction.get('count')) if transaction.get('count', False) else 0,
            'type': 'consumed',
            'state': 'confirm',
        }
        partner = self.env['res.partner'].sudo().search([('uuid', '=', transaction['odooContact'])])

        if partner:
            rec = partner.write({
                'transaction_ids': [(0, 0, data)],
            })
            if rec:
                return {'status_code': 200, "message": "Transaction Creation Successful"}
            else:
                return {'status_code': 500, "message": "Transaction Creation Failed"}
        else:
            return {'status_code': 404, "message": "Contact Not Found"}

    @api.model
    def _cron_update_epc_transactions(self):
        url = "https://dev.api-eport.kloudip.com/v1/organizations/epc"
        partners = self.search([('type', '=', 'invoice'), ('uuid', '!=', False)])
        for partner in partners:
            data = {
                'odooContact': partner.uuid,
                'count': partner.current_coin_balance
            }
            try:
                response = requests.patch(url, json=data)
                if response.status_code in [200, 204]:
                    _logger.info('EPC update successful {partner}-{balance}'.format(partner=partner.name, balance=partner.current_coin_balance))
            except requests.ConnectionError:
                _logger.info('EPC update failed {partner}-{balance}'.format(partner=partner.name, balance=partner.current_coin_balance))

    def generate_uuid(self):
        if self.type == 'invoice':
            id = uuid.uuid1()
            self.uuid = id.hex
