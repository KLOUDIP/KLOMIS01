# -*- coding: utf-8 -*-


""" File to manage the functions used while redirection"""

import logging
import pprint
import werkzeug
from odoo import http, SUPERUSER_ID
from odoo.http import request

_logger = logging.getLogger(__name__)


class PayHereController(http.Controller):

    """ Handles the redirection back from payment gateway to merchant site """

    AcceptUrl = '/payment/payhere/accept/'
    NotifyUrl = '/payment/payhere/notify/'
    CancelUrl = '/payment/payhere/cancel/'

    def _get_return_url(self, **post):
        """ Extract the return URL from the data coming from payhere. """
        return_url = post.pop('return_url', '')
        if not return_url:
            # website_sale_mod = request.env['ir.module.module'].sudo().search([('name', '=', 'website_sale')])
            # if website_sale_mod.state == 'installed':
            #     return_url = '/shop/payment/validate/'
            # else:
            return_url = '/payment/process'
        return return_url

    def payhere_validate_data(self, **post):
        """ Validate the data coming from payhere. """
        res = False
        reference = post['order_id']
        if reference:
            _logger.info('payhere: validated data')
            res = request.env['payment.transaction'].sudo().form_feedback(
                post, 'payhere_nisus')
            return res

    @http.route('/payment/payhere/notify', type='http', auth='public',
                methods=['POST'], csrf=False)
    def payhere_notify(self, **post):
        """ Gets the Post data from payhere after making payment """
        _logger.info('Beginning payhere Notify Return form_feedback with post data %s',
                     pprint.pformat(post))  # debug
        return_url = self._get_return_url(**post)
        _logger.info('Beginning payhere Notify Return form_feedback with post data %s',
                    pprint.pformat(post))
        self.payhere_validate_data(**post)
        return werkzeug.utils.redirect(return_url)

    @http.route('/payment/payhere/accept', type='http', auth="none", methods=['GET', 'POST'], csrf=False)
    def payhere_accept(self, **post):
        """ When acc accept its payhere payment: GET on this route """
        _logger.info('Beginning payhere accept with post data %s',
                     pprint.pformat(post))  # debug
        return_url = self._get_return_url(**post)
        return werkzeug.utils.redirect(return_url)

    @http.route('/payment/payhere/cancel', type='http', auth="none", csrf=False)
    def payhere_cancel(self, **post):
        """ When the user cancels its payhere payment: GET on this route """
        _logger.info('Beginning payhere cancel with post data %s',
                     pprint.pformat(post))  # debug
        return_url = self._get_return_url(**post)
        return werkzeug.utils.redirect(return_url)
