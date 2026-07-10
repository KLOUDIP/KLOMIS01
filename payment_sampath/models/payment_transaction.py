# -*- coding: utf-8 -*-
import uuid
import logging
import pprint
from urllib.parse import urljoin
from datetime import datetime

from odoo import _, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.payment_sampath.controllers.main import SampathController

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'sampath':
            return res

        base_url = self.provider_id.get_base_url()
        random_uuid = uuid.uuid4()

        payload = {
            "version": "1.5",
            "msgId": str(random_uuid),
            "operation": "PAYMENT_INIT",
            "requestDate": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z"),
            "validateOnly": False,
            "requestData": {
                "clientId": self.provider_id.sampath_client_id,
                "clientIdHash": "",
                "transactionType": "PURCHASE",
                "transactionAmount": {
                    "totalAmount": 0,
                    "paymentAmount": self.amount*100,
                    "serviceFeeAmount": 0,
                    'currency': self.currency_id.name if self.currency_id else 'LKR',
                },
                "redirect": {
                    "returnUrl": '%s' % urljoin(base_url, SampathController._return_url),
                    "cancelUrl": '%s' % urljoin(base_url, SampathController._return_url),
                    "returnMethod": "GET"
                },
                "clientRef": self.reference,
                "tokenize": self.tokenize,
                "useReliability": True,
            }
        }

        payment = self.provider_id._sampath_make_request(payload=payload)
        if payment.status_code == 200:
            response = payment.json()
            if response.get('msgId', False):
                self.write({'provider_reference': response.get('msgId', '')})

            rendering_values = {
                'reqid': response.get('responseData').get('reqid', ''),
                'api_url': response.get('responseData').get('paymentPageUrl')
            }

            return rendering_values

    def _sampath_tokenize_from_notification_data(self, notification_response):
        """ Create a payment.token from the PAYMENT_COMPLETE response data.

        Note: self.ensure_one()

        :param dict notification_response: The `responseData` dict of the
            PAYMENT_COMPLETE response returned by Paycorp.
        :return: None
        """
        self.ensure_one()

        # TODO: Confirm the exact field name(s) with the Paycorp integration
        # spec for your merchant profile. When `tokenize` is sent as True in
        # PAYMENT_INIT, the completion response carries the stored-card token;
        # the candidates below cover the shapes seen in Paycorp responses but
        # MUST be verified against a real sandbox response before go-live.
        credit_card_data = notification_response.get('creditCard') or {}
        provider_token = (
            notification_response.get('token')
            or credit_card_data.get('token')
            or credit_card_data.get('cardToken')
        )
        if not provider_token:
            _logger.warning(
                "Sampath: tokenization was requested for transaction %s but no token was found "
                "in the PAYMENT_COMPLETE response. Renewals will not be chargeable. "
                "Response data:\n%s", self.reference, pprint.pformat(notification_response)
            )
            return

        masked_pan = credit_card_data.get('number') or credit_card_data.get('maskedPan') or 'XXXX'
        token = self.env['payment.token'].create({
            'provider_id': self.provider_id.id,
            'payment_method_id': self.payment_method_id.id,
            'payment_details': masked_pan[-4:],
            'partner_id': self.partner_id.id,
            'provider_ref': provider_token,
        })
        self.write({
            'token_id': token.id,
            'tokenize': False,
        })
        _logger.info(
            "created token with id %(token_id)s for partner with id %(partner_id)s from "
            "transaction with reference %(ref)s",
            {'token_id': token.id, 'partner_id': self.partner_id.id, 'ref': self.reference},
        )

    def _send_payment_request(self):
        """ Override of payment to send a token-based payment request to Paycorp.

        Called by the subscription renewal cron (and Pay-by-token flows) to
        charge a saved card server-to-server, without customer redirection.

        Note: self.ensure_one()

        :return: None
        :raise UserError: If the transaction is not linked to a token.
        """
        super()._send_payment_request()
        if self.provider_code != 'sampath':
            return

        if not self.token_id:
            raise UserError("Sampath: " + _("The transaction is not linked to a token."))

        # TODO: Verify the exact operation name and requestData structure for a
        # tokenized (card-on-file) charge with the Paycorp integration doc.
        # PAYMENT_INIT with a `token` in requestData is the assumed shape; some
        # Paycorp profiles expose a dedicated token-payment operation instead.
        payload = {
            "version": "1.5",
            "msgId": str(uuid.uuid4()),
            "operation": "PAYMENT_INIT",
            "requestDate": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z"),
            "validateOnly": False,
            "requestData": {
                "clientId": self.provider_id.sampath_client_id,
                "clientIdHash": "",
                "transactionType": "PURCHASE",
                "transactionAmount": {
                    "totalAmount": 0,
                    "paymentAmount": self.amount * 100,
                    "serviceFeeAmount": 0,
                    "currency": self.currency_id.name if self.currency_id else 'LKR',
                },
                "clientRef": self.reference,
                "token": self.token_id.provider_ref,
                "useReliability": True,
            },
        }

        response = self.provider_id._sampath_make_request(payload=payload)
        json_response = response.json()
        _logger.info(
            "payment request response for transaction with reference %s:\n%s",
            self.reference, pprint.pformat(json_response)
        )
        if json_response.get('msgId'):
            self.write({'provider_reference': json_response['msgId']})

        # A server-to-server charge returns the final result directly; map it
        # through the same status handling as the redirect flow.
        response_data = json_response.get('responseData', {})
        status_code = response_data.get('responseCode', False)
        if status_code == "00":
            self._set_done()
        elif status_code in ("01", "02"):
            self._set_pending()
        else:
            self._set_error("Sampath: " + _("Token payment failed: %s", status_code))

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """ Override of payment to find the transaction based on Sampath data.

        :param str provider_code: The code of the provider that handled the transaction
        :param dict notification_data: The normalized notification data sent by the provider
        :return: The transaction if found
        :rtype: recordset of `payment.transaction`
        :raise: ValidationError if the data match no transaction
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'sampath' or len(tx) == 1:
            return tx

        reference = notification_data.get('clientRef', False)
        if reference:
            tx = self.search([('reference', '=', reference), ('provider_code', '=', 'sampath')])
            if not tx:
                raise ValidationError("Sampath: " + _("No transaction found matching reference %s.", reference))
        else:  # FIXME: Handle status code 500
            error = 'Unknown error occurred when processing the transaction with Sampath (Payment Already confirmed ' \
                    'with bank but not with our system please contact our hotline)'
            _logger.warning(error)
            raise ValidationError(error)

        return tx

    def _process_notification_data(self, notification_data):
        """ Override of payment to process the transaction based on Sampath data.

        Note: self.ensure_one()

        :param dict notification_data: The normalized notification data sent by the provider
        :return: None
        :raise: ValidationError if inconsistent data were received
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'sampath':
            return

        json_response = notification_data.json()
        notification_response = json_response.get('responseData', {})

        status_code = notification_response.get('responseCode', False)
        if status_code == "00":
            if self.tokenize:
                self._sampath_tokenize_from_notification_data(notification_response)
            self._set_done()
        elif status_code == "01" or status_code == "02":
            self._set_pending()
        elif status_code == "VA":
            self._set_canceled(_("Invalid Card Number"))
        else:
            _logger.warning(
                "received data with invalid payment status (%s) for transaction with reference %s",
                status_code, self.reference
            )
            self._set_error("Sampath: " + _("payment Failed: %s", status_code))