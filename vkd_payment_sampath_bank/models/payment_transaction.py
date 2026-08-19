from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
import json

from odoo.http import request
from urllib.parse import urljoin, urlencode
import requests
import datetime
import urllib.parse
from odoo.addons.vkd_payment_sampath_bank.controllers.main import SampathbankPaymentProvider

import logging
_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    sampathbank_reqid = fields.Char('Request ID', help="A unique payment id provided by Paycorp")
    sampathbank_expireAt = fields.Char('Expires at', help="Time at wich this reuest will expire.")

    def _get_specific_processing_values(self, processing_values):
        """ Override of payment to return Sampath Bank-specific processing values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic processing values of the transaction
        :return: The dict of provider-specific processing values
        :rtype: dict
        """
        res = super()._get_specific_processing_values(processing_values)
        if self.provider_code != 'sampathbank':
            return res

        return {
            'payment_transaction_id': self.id,  # We are redirecting to another page to get the payment gateway specific values, but because we need to send json, we can not do as the other providers.
        }

    def _search_by_reference(self, provider_code, payment_data):
        """ Override of payment to find the transaction based on Sampath Bank data.

        Odoo 19 renamed `_get_tx_from_notification_data` -> `_search_by_reference`
        and the `notification_data` argument -> `payment_data`.

        :param str provider_code: The code of the provider that handled the transaction
        :param dict payment_data: The payment data sent by the provider
        :return: The transaction if found
        :rtype: recordset of `payment.transaction`
        :raise: ValidationError if inconsistent data were received
        :raise: ValidationError if the data match no transaction
        """
        tx = super()._search_by_reference(provider_code, payment_data)
        if provider_code != 'sampathbank':
            return tx

        return self.search([('sampathbank_reqid', '=', payment_data.get('reqid'))])

    def _apply_updates(self, payment_data):
        """ Override of payment to update the transaction based on Sampath Bank data.

        Odoo 19 renamed `_process_notification_data` -> `_apply_updates`.

        Note: self.ensure_one()

        :param dict payment_data: The payment data sent by the provider
        :return: None
        :raise: ValidationError if inconsistent data were received
        """
        super()._apply_updates(payment_data)
        if self.provider_code != 'sampathbank':
            return

        data = {
            'operation': 'PAYMENT_COMPLETE',
            'validateOnly': False,
            'requestData': {
                'clientId': self.provider_id.sampathbank_clientId,
                'reqid': self.sampathbank_reqid,
            },
        }

        url = self.provider_id._get_sampathbank_url()
        response = requests.post(
            url + '/rest/service/proxy',
            json=data,
            headers=self._get_sampath_bank_headers())

        # `response.content` is raw bytes; parse the JSON body to read the result.
        response_data = response.json().get('responseData', {})
        if response_data.get('responseCode') == '00':
            self._set_done()
        else:
            self._set_canceled()

    ############################
    # Sampath specific methods #
    # ##########################

    def _get_sampath_bank_headers(self):
        """
        Returns the header used for requests to Sampath bank
        """
        self.ensure_one()
        vals = {
            'AUTHTOKEN': self.provider_id.sampathbank_authtoken,
            # 'HMAC': self.provider_id.sampathbank_hmac_secret,
        }
        return vals

    @api.model
    def _get_base_url(self):
        return self.env['ir.config_parameter'].sudo().get_param('web.base.url')

    def get_sampathbank_payment_init_url(self, reference):
        # if self.reference != reference:
        if self.id != reference:
            ValidationError("Sampath Bank: " + _("Received tampered payment request data!"))

        url = self.provider_id._get_sampathbank_url()
        data = self._get_sampathbank_payment_init_vals()

        response = requests.post(
            url + '/rest/service/proxy',
            json=data,
            headers=self._get_sampath_bank_headers()
        ).text
        response = json.loads(response)
        self.write({
            'sampathbank_expireAt': response['responseData']['expireAt'],
            'sampathbank_reqid': response['responseData']['reqid'],
        })

        return response['responseData']['paymentPageUrl']

    def _get_sampathbank_return_url(self):
        base_url = self._get_base_url()

        params = {
            'reqid': self.sampathbank_reqid
        }
        y = urljoin(base_url, '/payment/sampathbank/confirm') + urlencode(params)
        return urljoin(base_url, '/payment/sampathbank/confirm')

    def _get_sampathbank_payment_init_vals(self):
        base_url = self._get_base_url()
        data = {
            'version': '1.5',
            'msgId': 'AD32B8FC-0D72-41D3-8F6B-51FB2107835E',
            'operation': 'PAYMENT_INIT',
            'requestDate': str(datetime.datetime.now()),
            'validateOnly': False,
            'requestData': {
                'clientId': self.provider_id.sampathbank_clientId,
                'transactionType': 'PURCHASE',
                'transactionAmount': {
                    # 'paymentAmount': self.amount,
                    'paymentAmount': 20000,
                    # 'currency': self.currency_id.name
                    'currency': 'LKR'
                }
            },
            'redirect': {
                'returnUrl': '',
                'cancelUrl': '',
                'returnMethod': 'GET'
                # 'returnUrl': '%s' % urljoin(base_url, SampathbankPaymentProvider.AcceptUrl),
            },
            'clientRef': self.reference,  # Change it to something else, if it makes sense to use maybe the transaction id instead.
            'tokenize': False,
        }

        return data
