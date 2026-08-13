# -*- coding: utf-8 -*-
import uuid
import logging
from urllib.parse import urljoin
from datetime import datetime
from odoo import _, models
from odoo.exceptions import ValidationError
from odoo.addons.payment_sampath.controllers.main import SampathController

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _get_specific_rendering_values(self, processing_values):
        """ Override to initiate Sampath payment """
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
                    "paymentAmount": int(self.amount * 100),
                    "serviceFeeAmount": 0,
                    'currency': self.currency_id.name if self.currency_id else 'LKR',
                },
                "redirect": {
                    "returnUrl": urljoin(base_url, SampathController._return_url),
                    "cancelUrl": urljoin(base_url, SampathController._return_url),
                    "returnMethod": "GET"
                },
                "clientRef": self.reference,
                "tokenize": False,
                "useReliability": True,
            }
        }

        # Payment Init Request
        response = self.provider_id._sampath_make_request(payload=payload)
        if response.status_code == 200:
            json_response = response.json()
            # CRITICAL: Populate provider_reference in the INIT phase
            if json_response.get('msgId'):
                self.write({'provider_reference': json_response.get('msgId')})

            return {
                'reqid': json_response.get('responseData', {}).get('reqid', ''),
                'api_url': json_response.get('responseData', {}).get('paymentPageUrl')
            }
        return res

    def _process_notification_data(self, notification_data):
        """ Override to strictly handle status transitions """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'sampath':
            return

        # Ensure notification_data is handled safely
        if hasattr(notification_data, 'json'):
            json_response = notification_data.json()
        else:
            json_response = notification_data

        notification_response = json_response.get('responseData', {})
        status_code = notification_response.get('responseCode')

        # Map Sampath response codes to Odoo transaction states
        if status_code == "00":
            self._set_done()
        elif status_code in ["01", "02"]:
            self._set_pending()
        elif status_code == "VA":
            self._set_canceled(_("Invalid Card Number or Payment Cancelled"))
        else:
            error_msg = _("Sampath: Payment Failed with code %s", status_code)
            _logger.warning("Payment failed for transaction %s: %s", self.reference, error_msg)
            self._set_error(error_msg)
