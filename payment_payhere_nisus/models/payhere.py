# -*- coding: utf-8 -*-



""" This file manages all the operations and the functionality of the gateway
integration """

import json
import logging
import re
from werkzeug import urls
from urllib.request import urlopen
from urllib.parse import urljoin
from odoo import http
from odoo.http import request
from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.addons.payment_payhere_nisus.controllers.main import PayHereController
from odoo import fields, models
from openerp.tools.translate import _

_logger = logging.getLogger(__name__)


class AcquirerPayHere(models.Model):

    """ Class to handle all the functions required in integration """
    _inherit = 'payment.acquirer'

    def _get_payhere_urls(self, state):
        """ payhere URLS """
        if state == 'enabled':
            return {
                'payhere_form_url':
                    'https://www.payhere.lk/pay/checkout'
            }
        else:
            return {
                'payhere_form_url':
                    'https://sandbox.payhere.lk/pay/checkout'
            }

    provider = fields.Selection(selection_add=[('payhere_nisus',
                                                'PayHere')])
    payhere_merchant_number = fields.Char('Payhere Merchant Number',
                                          required_if_provider='payhere_nisus')

    def payhere_nisus_form_generate_values(self, values):
        """ Gathers the data required to make payment """
        #base_url = self.env['ir.config_parameter'].get_param('web.base.url')

        url = str(http.request.httprequest)
        #urls = re.findall('http?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', url)
        #parsed_uri = urlopen(urls[0])
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')

        payhere_tx_values = dict(values)
        payhere_tx_values.update({
            'merchant_id': self.payhere_merchant_number,
            'currency': values['currency'].name,
            'amount': str(int(values['amount'])) or '',
            'order_id': values['reference'] or '',
            'notify_url': '%s' % urljoin(base_url, PayHereController.NotifyUrl),
            'cancel_url': '%s' % urljoin
            (base_url, PayHereController.CancelUrl),
            'return_url': '%s' % urljoin(base_url, PayHereController.AcceptUrl),
            'first_name': values['billing_partner_name'] or '',
            'last_name': 'Test',
            'email': values['billing_partner_email'] or '',
            'address': values['billing_partner_address'] or '',
            'phone': values['billing_partner_phone'] or '',
            'city': values['billing_partner_city'] or '',
            'country': values['billing_partner_country'].name or '',
            'items': values['reference'] or '',
        })
        return payhere_tx_values

    def payhere_nisus_get_form_action_url(self):
        """ Gets the Url of the payment form of payhere """
        return self._get_payhere_urls(self.state)['payhere_form_url']


class TxPayHere(models.Model):

    """ Handles the functions for validation after transaction is processed """
    _inherit = 'payment.transaction'

    # --------------------------------------------------
    # FORM RELATED METHODS
    # --------------------------------------------------

    def _payhere_nisus_form_get_tx_from_data(self, data):
        """ Given a data dict coming from payhere, verify it and find '
        'the related transaction record. Create a payment method if '
        'an alias is returned."""

        if data['payment_id']:
            reference = data.get('order_id')
            if not reference:
                error_msg = _(
                    'Payhere: received data with missing reference (%s)'
                ) % (reference)
                _logger.info(error_msg)
                raise ValidationError(error_msg)

            tx_ids = self.env['payment.transaction'
                                ].search([('reference', '=', reference)])
            if not tx_ids or len(tx_ids) > 1:
                error_msg = 'Payhere: received data for reference %s' % (
                    reference)
                if not tx_ids:
                    error_msg += '; no order found'
                else:
                    error_msg += '; multiple order found'
                _logger.info(error_msg)
                raise ValidationError(error_msg)
            return tx_ids[0]

    def _payhere_nisus_form_validate(self, data):
        """ Verify the validity of data coming from payhere"""
        res = {}
        if data['payment_id']:
            _logger.info(
                'Validated payhere payment for tx %s: set as '
                'done' % (self.reference))
            res.update(state='done', date=data.get(
                'payment_date', fields.datetime.now()))
            sales_orders = self.sale_order_ids.filtered(lambda so: so.state == 'draft')
            sales_orders._send_order_confirmation_mail()
            return self.write(res)
        else:
            error = 'Received unrecognized data for payhere payment %s,' \
                ' set as error' % (self.reference)
            _logger.info(error)
            res.update(state='error', state_message=error)
            self.write(res)
