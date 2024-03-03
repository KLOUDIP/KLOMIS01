# -*- coding: utf-8 -*-
import logging
from hashlib import md5

from odoo import fields, models, _
from odoo.addons.payment_payhere_nisus import const

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(selection_add=[('payhere_nisus', "PayHere")], ondelete={'payhere_nisus': 'set default'})
    payhere_merchant_number = fields.Char(string='Payhere Merchant Number', required_if_provider='payhere_nisus')
    payhere_merchant_secret = fields.Char(string="PayHere Merchant Secret", required_if_provider='payhere')

    def _payhere_nisus_get_api_url(self):
        """ payhere URLS """
        if self.state == 'enabled':
            return 'https://www.payhere.lk/pay/checkout'
        else:
            return 'https://sandbox.payhere.lk/pay/checkout'

    def _payhere_generate_sign(self, inout, values):
        if inout not in ('in', 'out'):
            raise Exception("Type must be 'in' or 'out'....")
        merchant_secret_md5 = (md5((self.payhere_merchant_secret).encode('utf-8')).hexdigest()).upper()
        if inout == 'in':
            # hash = to_upper_case(md5(merchant_id + order_id + amount + currency + to_upper_case(md5(merchant_secret))))
            data_to_hash = (self.payhere_merchant_number + values['order_id'] +
                            format(values['amount'], '.2f') + values['currency'] + merchant_secret_md5)
        else:
            data_to_hash = (self.payhere_merchant_number + values['order_id'] +
                            str(values['payhere_amount']) + values['payhere_currency'] +
                            values['status_code'] + merchant_secret_md5)

        return (md5(data_to_hash.encode('utf-8')).hexdigest()).upper()

    def _get_default_payment_method_codes(self):
        """ Override of `payment` to return the default payment method codes. """
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'payhere_nisus':
            return default_codes
        return const.DEFAULT_PAYMENT_METHODS_CODES
