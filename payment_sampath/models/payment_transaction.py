# -*- coding: utf-8 -*-
import uuid
import logging
from urllib.parse import urljoin
from datetime import datetime
from markupsafe import Markup

from odoo import _, api, models
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
    # Odoo 19 notification hooks. `_process()` runs, in this order:
    #   _search_by_reference -> _validate_amount (-> _extract_amount_data)
    #   -> _apply_updates
    # ------------------------------------------------------------------

    @api.model
    def _extract_reference(self, provider_code, payment_data):
        """ Return the Odoo reference Paycorp echoes back as `clientRef`. """
        if provider_code != 'sampath':
            return super()._extract_reference(provider_code, payment_data)
        response_data = (payment_data or {}).get('responseData') or {}
        return payment_data.get('clientRef') or response_data.get('clientRef')

    @api.model
    def _search_by_reference(self, provider_code, payment_data):
        """ Find the transaction from the `reqid` (primary) or `clientRef`. """
        if provider_code != 'sampath':
            return super()._search_by_reference(provider_code, payment_data)

        tx = self.browse()
        reqid = payment_data.get('reqid')
        if reqid:
            tx = self.search([
                ('provider_reference', '=', reqid),
                ('provider_code', '=', 'sampath'),
            ], limit=1)
        if not tx:
            client_ref = self._extract_reference(provider_code, payment_data)
            if client_ref:
                tx = self.search([
                    ('reference', '=', client_ref),
                    ('provider_code', '=', 'sampath'),
                ], limit=1)
        if not tx:
            _logger.warning(
                "Sampath: no transaction found for reqid %s / clientRef %s",
                reqid, payment_data.get('clientRef'),
            )
        return tx

    def _extract_amount_data(self, payment_data):
        """ Give `_validate_amount` the amount Paycorp actually charged.

        Without this override the base method returns `{}` and
        `_validate_amount` crashes with KeyError('amount') *before*
        `_apply_updates` runs, so the transaction never leaves draft: no
        "confirmed" message, no order confirmation, no account.payment.
        """
        if self.provider_code != 'sampath':
            return super()._extract_amount_data(payment_data)

        response_data = (payment_data or {}).get('responseData') or {}
        if response_data.get('responseCode') != '00':
            return None  # Nothing was charged; _apply_updates sets the failure state.

        amount_vals = response_data.get('transactionAmount') or {}
        minor_amount = amount_vals.get('paymentAmount')
        if minor_amount in (None, ''):
            _logger.warning(
                "Sampath: PAYMENT_COMPLETE for %s carries no paymentAmount, "
                "skipping the amount check. responseData: %s",
                self.reference, response_data,
            )
            return None

        return {
            # PAYMENT_INIT sends the amount in minor units (cents); Paycorp
            # echoes it back the same way.
            'amount': float(minor_amount) / 100.0,
            'currency_code': amount_vals.get('currency') or self.currency_id.name,
            'precision_digits': 2,
        }

    def _apply_updates(self, payment_data):
        """ Set the transaction state from the PAYMENT_COMPLETE response. """
        super()._apply_updates(payment_data)
        if self.provider_code != 'sampath':
            return

        response_data = (payment_data or {}).get('responseData') or {}
        status_code = response_data.get('responseCode')
        response_text = response_data.get('responseText') or ''

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
                desc=response_text or _("no detail"),
            )
            _logger.warning("Payment failed for transaction %s: %s", self.reference, error_msg)
            self._set_error(error_msg)

        self._sampath_log_gateway_response(response_data)

    def _sampath_log_gateway_response(self, response_data):
        """ Post the Paycorp result on the linked sale order / invoice chatter. """
        self.ensure_one()
        card = response_data.get('creditCard') or {}
        details = [
            (_("Transaction"), self.reference),
            (_("Status"), "%s %s" % (response_data.get('responseCode') or '',
                                    response_data.get('responseText') or '')),
            (_("Paycorp txn reference"), response_data.get('txnReference')),
            (_("Auth code"), response_data.get('authCode')),
            (_("Card"), card.get('number')),
            (_("Paycorp reqid"), self.provider_reference),
        ]
        rows = Markup('').join(
            Markup('<li>%s: %s</li>') % (label, value)
            for label, value in details if value and str(value).strip()
        )
        message = Markup('<p>%s</p><ul>%s</ul>') % (
            _("Sampath Bank (Paycorp) payment response"), rows,
        )
        self._log_message_on_linked_documents(message)
