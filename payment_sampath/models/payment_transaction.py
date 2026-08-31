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
        """ Override to initiate the Sampath (Paycorp) payment. """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'sampath':
            return res

        base_url = self.provider_id.get_base_url()
        payload = {
            "version": "1.5",
            "msgId": str(uuid.uuid4()),
            "operation": "PAYMENT_INIT",
            # Paycorp rejects a microsecond timestamp with no offset. Send a
            # timezone-aware ISO-8601 value (e.g. 2026-08-31T14:05:09+05:30).
            "requestDate": datetime.now().astimezone().isoformat(timespec='seconds'),
            "validateOnly": False,
            "requestData": {
                "clientId": self.provider_id.sampath_client_id,
                "clientIdHash": "",
                "transactionType": "PURCHASE",
                "transactionAmount": {
                    "totalAmount": 0,
                    # Paycorp expects the amount in minor units (cents).
                    "paymentAmount": int(round(self.amount * 100)),
                    "serviceFeeAmount": 0,
                    "currency": self.currency_id.name if self.currency_id else 'LKR',
                },
                "redirect": {
                    "returnUrl": urljoin(base_url, SampathController._return_url),
                    "cancelUrl": urljoin(base_url, SampathController._return_url),
                    "returnMethod": "GET",
                },
                "clientRef": self.reference,
                "tokenize": False,
                "useReliability": True,
            },
        }

        data = self.provider_id._sampath_make_request(payload=payload)
        response_data = data.get('responseData') or {}

        response_code = response_data.get('responseCode')
        payment_page_url = response_data.get('paymentPageUrl')
        if not payment_page_url:
            _logger.error(
                "Sampath: PAYMENT_INIT returned no paymentPageUrl for %s: %s",
                self.reference, data,
            )
            raise ValidationError("Sampath: " + _(
                "The gateway did not return a payment page (responseCode %(code)s, %(desc)s).",
                code=response_code or 'n/a',
                desc=response_data.get('responseText') or data.get('message') or _("no detail"),
            ))

        # Keep the gateway's own handle on this transaction so the return route
        # can find it again.
        self.provider_reference = response_data.get('reqid') or data.get('msgId') or ''

        return {
            'reqid': response_data.get('reqid', ''),
            'api_url': payment_page_url,
        }

    # ------------------------------------------------------------------
    # Odoo 19 renamed the notification hooks:
    #   _get_tx_from_notification_data -> _search_by_reference
    #   _process_notification_data     -> _apply_updates
    #   _handle_notification_data      -> _process
    # ------------------------------------------------------------------

    def _search_by_reference(self, provider_code, payment_data):
        """ Find the transaction from the `reqid` Paycorp sends back. """
        tx = super()._search_by_reference(provider_code, payment_data)
        if provider_code != 'sampath':
            return tx

        reqid = payment_data.get('reqid')
        client_ref = payment_data.get('clientRef')
        if reqid:
            tx = self.search([
                ('provider_reference', '=', reqid),
                ('provider_code', '=', 'sampath'),
            ], limit=1)
        if not tx and client_ref:
            tx = self.search([
                ('reference', '=', client_ref),
                ('provider_code', '=', 'sampath'),
            ], limit=1)
        if not tx:
            raise ValidationError("Sampath: " + _(
                "No transaction found matching reqid %s.", reqid,
            ))
        return tx

    def _apply_updates(self, payment_data):
        """ Set the transaction state from the PAYMENT_COMPLETE response. """
        super()._apply_updates(payment_data)
        if self.provider_code != 'sampath':
            return

        response_data = (payment_data or {}).get('responseData') or {}
        status_code = response_data.get('responseCode')

        if status_code == "00":
            self._set_done()
        elif status_code in ("01", "02"):
            self._set_pending()
        elif status_code == "VA":
            self._set_canceled(_("Invalid Card Number or Payment Cancelled"))
        else:
            error_msg = _(
                "Sampath: payment failed with code %(code)s (%(desc)s)",
                code=status_code or 'n/a',
                desc=response_data.get('responseText') or _("no detail"),
            )
            _logger.warning("Payment failed for transaction %s: %s", self.reference, error_msg)
            self._set_error(error_msg)
