# -*- coding: utf-8 -*-
import logging
import pprint
import uuid
from datetime import datetime

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SampathController(http.Controller):
    _return_url = '/payment/sampath/return'

    def _confirm_sampath_transaction(self, tx, payment_response):
        """ Run PAYMENT_COMPLETE with the transaction's OWN provider.

        Searching `payment.provider` by code (limit=1) could return the record
        of another company (KLOUDIP INC vs KLOUDIP (Pvt) Ltd) or a disabled
        copy with different credentials, so the provider is taken from the tx.
        """
        provider = tx.provider_id.sudo()
        values = {
            "version": "1.5",
            "operation": "PAYMENT_COMPLETE",
            "msgId": str(uuid.uuid4()),
            "requestDate": datetime.now().astimezone().isoformat(timespec='seconds'),
            "validateOnly": False,
            "requestData": {
                "clientId": provider.sampath_client_id,
                "reqid": payment_response.get('reqid') or tx.provider_reference,
            },
        }
        return provider._sampath_make_request(values)

    @http.route(_return_url, type='http', auth='public', methods=['POST', 'GET'],
                csrf=False, save_session=False)
    def sampath_return_from_checkout(self, **raw_data):
        """ Return route hit by Paycorp after the shopper leaves the hosted page. """
        _logger.info("Redirected from Sampath with data: %s", pprint.pformat(raw_data))

        Transaction = request.env['payment.transaction'].sudo()
        tx = Transaction._search_by_reference('sampath', raw_data)
        if not tx:
            return request.redirect('/payment/status')

        # Paycorp may redirect twice (refresh / back button). Do not call
        # PAYMENT_COMPLETE again on a transaction that is already final.
        if tx.state in ('done', 'cancel'):
            return request.redirect('/payment/status')

        try:
            confirm_response = self._confirm_sampath_transaction(tx, raw_data)
            confirm_response.setdefault('reqid', raw_data.get('reqid'))
            confirm_response.setdefault('clientRef', raw_data.get('clientRef'))
            # Call `_process` on the tx itself so it does not search again.
            tx._process('sampath', confirm_response)
        except Exception as e:  # noqa: BLE001 - never leave the shopper on a 500
            _logger.exception("Sampath: could not complete transaction %s", tx.reference)
            request.env.cr.rollback()
            tx = Transaction.browse(tx.id)
            tx._log_message_on_linked_documents(
                "Sampath Bank: PAYMENT_COMPLETE failed for %s: %s" % (tx.reference, e)
            )

        # Make sure the order gets confirmed and the payment gets created even
        # if the /payment/status poll never runs (session lost on the way back
        # from the bank, shopper closes the tab, ...).
        cron = request.env.ref('payment.cron_post_process_payment_tx', raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger()

        return request.redirect('/payment/status')
