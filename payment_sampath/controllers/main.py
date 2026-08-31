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

    def _confirm_sampath_transaction(self, payment_response):
        """ Run PAYMENT_COMPLETE and return the parsed gateway answer (a dict). """
        provider = request.env['payment.provider'].sudo().search(
            [('code', '=', 'sampath')], limit=1,
        )

        values = {
            "version": "1.5",
            "operation": "PAYMENT_COMPLETE",
            "msgId": str(uuid.uuid4()),
            "requestDate": datetime.now().astimezone().isoformat(timespec='seconds'),
            "validateOnly": False,
            "requestData": {
                "clientId": provider.sampath_client_id,
                "reqid": payment_response.get('reqid'),
            },
        }
        return provider._sampath_make_request(values)

    @http.route(_return_url, type='http', auth='public', methods=['POST', 'GET'],
                csrf=False, save_session=False)
    def sampath_return_from_checkout(self, **raw_data):
        """ Return route hit by Paycorp after the shopper leaves the hosted page. """
        _logger.info("Redirected from Sampath with data: %s", pprint.pformat(raw_data))

        # PAYMENT_COMPLETE gives the authoritative status; carry `reqid` through
        # so `_search_by_reference` can still locate the transaction.
        confirm_response = self._confirm_sampath_transaction(raw_data)
        confirm_response.setdefault('reqid', raw_data.get('reqid'))

        # Odoo 19: `_handle_notification_data` was renamed to `_process`.
        request.env['payment.transaction'].sudo()._process('sampath', confirm_response)

        return request.redirect('/payment/status')
