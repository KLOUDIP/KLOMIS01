import logging
import pprint

from odoo import _, http
from odoo.http import request
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SampathbankPaymentProvider(http.Controller):
    AcceptUrl = '/payment/sampathbank/confirm'

    @http.route(AcceptUrl, type='http', auth='public', methods=['GET'], csrf=False)
    def sampathbank_confirm(self, **kwargs):
        """ Gets the data from sampathbank after making payment

        Odoo 19: `_handle_notification_data` -> `_process`. It internally calls
        `_search_by_reference` then `_apply_updates`.
        """
        _logger.info('Beginning sampathbank Return form_feedback with post data %s', pprint.pformat(kwargs))  # debug
        request.env['payment.transaction'].sudo()._process('sampathbank', kwargs)
        return request.redirect('/payment/status')
