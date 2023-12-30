import logging
import pprint

from odoo import _, http
from odoo.http import request
from odoo.exceptions import ValidationError

from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing

import logging
_logger = logging.getLogger(__name__)


class SampathbankPaymentProvider(http.Controller):
    AcceptUrl = '/payment/sampathbank/confirm'

    @http.route(AcceptUrl, type='http', auth='public', methods=['GET'], csrf=False)
    def sampathbank_confirm(self, **kwargs):
        """ Gets the Post data from sampathbank after making payment """
        _logger.info('Beginning sampathbank Return form_feedback with post data %s', pprint.pformat(kwargs))  # debug
        request.env['payment.transaction'].sudo()._handle_notification_data('sampathbank', kwargs)
        return request.redirect('/payment/status')


