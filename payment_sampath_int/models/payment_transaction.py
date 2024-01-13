# -*- coding: utf-8 -*-
import uuid
import logging
from urllib.parse import urljoin
from datetime import datetime

from odoo import _, models
from odoo.exceptions import ValidationError

from odoo.addons.payment_sampath_int.controllers.main import SampathIntController

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'sampath_int':
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
                "clientId": self.provider_id.sampath_int_client_id,
                "clientIdHash": "",
                "transactionType": "PURCHASE",
                "transactionAmount": {
                    "totalAmount": 0,
                    "paymentAmount": self.amount*100,
                    "serviceFeeAmount": 0,
                    'currency': self.currency_id.name if self.currency_id else 'USD',
                },
                "redirect": {
                    "returnUrl": '%s' % urljoin(base_url, SampathIntController._return_url),
                    "cancelUrl": '%s' % urljoin(base_url, SampathIntController._return_url),
                    "returnMethod": "GET"
                },
                "clientRef": self.reference,
                "tokenize": False,
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

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """ Override of payment to find the transaction based on Sampath data.

        :param str provider_code: The code of the provider that handled the transaction
        :param dict notification_data: The normalized notification data sent by the provider
        :return: The transaction if found
        :rtype: recordset of `payment.transaction`
        :raise: ValidationError if the data match no transaction
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'sampath_int' or len(tx) == 1:
            return tx

        reference = notification_data.get('clientRef', False)
        if reference:
            tx = self.search([('reference', '=', reference), ('provider_code', '=', 'sampath_int')])
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
        json_response = notification_data.json()
        notification_response = json_response.get('responseData', {})
        super()._process_notification_data(notification_response)
        if self.provider_code != 'sampath_int':
            return

        status_code = notification_response.get('responseCode', False)
        if status_code == "00":
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