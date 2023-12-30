# -*- coding: utf-8 -*-
import json
import logging

import werkzeug.wrappers


from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class EportController(http.Controller):

    @http.route('/v1/epc/create_transaction', methods=['POST'], type='json', auth='public', csrf=False)
    def api_get_employee(self, **kw):
        try:
            data = json.loads(request.httprequest.data)
            _logger.info(f'Received data: {data}')
            if data:
                status = request.env['res.partner'].sudo().create_transaction(data)
                return status
            else:
                return {'message': 'Json object is empty', 'error': "Bad Request", 'status_code': 500}

        except Exception as e:
            _logger.info(e.__str__())
            return {'message': e.__str__(), 'error': "Transaction creation failed", 'status_code': 500}
