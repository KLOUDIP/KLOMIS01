# -*- coding: utf-8 -*-
""" File to manage the functions used while redirection"""

import logging
import pprint

from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo.tools import consteq

_logger = logging.getLogger(__name__)


class PayHereController(http.Controller):

    """ Handles the redirection back from payment gateway to merchant site """

    _return_url = '/payment/payhere/return'
    _notify_url = '/payment/payhere/notify'
    _cancel_url = '/payment/payhere/cancel'
    _webhook_url = '/payment/payhere/webhook'

    @http.route([_notify_url, _cancel_url],  type='http', auth='public', csrf=False)
    def payhere_notify_from_checkout(self, **data):
        """ Process the notification data sent by Payhere after redirection from checkout.
        :param dict data: The notification data
        """
        _logger.info("handling redirection from Payhere with data:\n%s", pprint.pformat(data))

        # Check the integrity of the notification
        tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data('payhere_nisus', data)
        self._verify_notification_signature(data, tx_sudo)

        # Handle the notification data
        tx_sudo._handle_notification_data('payhere_nisus', data)
        return request.redirect('/payment/status')

    @http.route(_return_url, type='http', auth='public', csrf=False)
    def payhere_return_from_checkout(self, **data):
        """ Process the notification data sent by Payhere after redirection from checkout.
        :param dict data: The notification data
        """
        _logger.info("handling redirection from Payhere with data:\n%s", pprint.pformat(data))

        # Check the integrity of the notification
        # tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data('payhere_nisus', data)

        # Handle the notification data
        # tx_sudo._handle_notification_data('payhere_nisus', data)
        return request.redirect('/payment/status')

    @http.route(_webhook_url, type='http', methods=['POST'], auth='public', csrf=False)
    def payhere_webhook(self, **data):
        """ Process the notification data sent by Payhere to the webhook."""

        _logger.info("notification received from Payhere with data:\n%s", pprint.pformat(data))
        try:
            # Check the origin and integrity of the notification
            tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
                'payhere_nisus', data
            )
            self._verify_notification_signature(data, tx_sudo)

            # Handle the notification data
            tx_sudo._handle_notification_data('payhere_nisus', data)
        except ValidationError:  # Acknowledge the notification to avoid getting spammed
            _logger.exception("unable to handle the notification data; skipping to acknowledge")

        return 'SUCCESS'  # Acknowledge the notification

    @staticmethod
    def _verify_notification_signature(notification_data, tx_sudo):
        """ Check that the received signature matches the expected one.

        :param dict notification_data: The notification data
        :param recordset tx_sudo: The sudoed transaction referenced by the notification data, as a
                                  `payment.transaction` record
        :return: None
        :raise: :class:`werkzeug.exceptions.Forbidden` if the signatures don't match
        """
        # Retrieve the received signature from the data
        received_signature = notification_data.get('md5sig')
        if not received_signature:
            _logger.warning("received notification with missing signature")
            raise Forbidden()

        # Compare the received signature with the expected signature computed from the data
        expected_signature = tx_sudo.provider_id._payhere_generate_sign('out', notification_data)
        if not (consteq(received_signature, expected_signature) and notification_data.get('status_code') == '2'):
            _logger.warning("received notification with invalid signature")
            raise Forbidden()
