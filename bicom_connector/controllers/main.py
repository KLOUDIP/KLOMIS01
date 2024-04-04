# -*- coding: utf-8 -*-

import json
import logging
import requests

import xmlrpc.client

from odoo import http, SUPERUSER_ID
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class UserExtensionController(http.Controller):

    @http.route('/token', type='http', auth='none', methods=['GET', 'POST'], csrf=False)
    def get_token(self, **kwargs):
        """
        Authenticate with odoo server and get user extension
        """
        try:
            _logger.info('Data has been successfully received')
            db_name = request.db  # TODO: change the database name
            username = request.httprequest.authorization.get('username')
            password = request.httprequest.authorization.get('password')
            user_id = request.session.authenticate(db_name, username, password)
            user_token = request.env['res.users'].sudo().browse(user_id).uuid_token
            if user_token:
                response = Response(json.dumps({"id": user_token}), status=200, content_type='application/json')
                return response
            else:
                response = Response(json.dumps({"error": "Access token not configured"}), status=400, content_type='application/json')
                return response
        except Exception as e:
            status, status_code = {'error': str(e)}, 403
        _logger.info("status")
        return Response(json.dumps(status), status=status_code, content_type='application/json')

    @http.route(['/customers', '/customers/search', ], type='http', auth='none', methods=['GET'], csrf=False)
    def get_customers(self, **kwargs):
        uuid_token = request.httprequest.headers.get('X-CrmIService-Token')
        domain = []
        user = request.env['res.users'].sudo().search([('uuid_token', '=', uuid_token)])
        phonenumber = kwargs.get('phonenumber', '').strip()
        if phonenumber != '':
            domain.append(('phone_sanitized', '=', '+'+phonenumber))
        if user:
            customers = request.env['res.partner'].with_user(user).search(domain)
            customer_list = [{
                "id": rec.id,
                "type": rec.type,
                "webpage": "",
                "name": rec.name,
                "email": rec.email,
                "company": rec.company_id.name if rec.company_id else '',
                "mobilephone": rec.mobile,
                "workphone": None,
                "homephone": rec.phone,
                "fax": None
            } for rec in customers]
            response = Response(json.dumps(customer_list), status=200, content_type='application/json')
            return response
        else:
            response = Response(json.dumps({"error": "Invalid or missing authorization token"}), status=401, content_type='application/json')
            return response

    @http.route(['/crm'], type='http', auth='none', methods=['GET'], csrf=False)
    def get_crm_info(self, **kwargs):
        uuid_token = request.httprequest.headers.get('X-CrmIService-Token')
        user = request.env['res.users'].sudo().search([('uuid_token', '=', uuid_token)])
        if user:
            if user.company_id:
                data = {'name': user.company_id[0].name, 'url': user.company_id[0].website, 'version': '1.0.1'}
                response = Response(json.dumps(data), status=200, content_type='application/json')
                return response
            else:
                response = Response(json.dumps({"error": "No information about CRM"}), status=401, content_type='application/json')
                return response
        else:
            response = Response(json.dumps({"error": "Invalid or missing authorization token"}), status=401, content_type='application/json')
            return response

    @http.route(['/calllog', '/calllog/<int:id>'], type='http', auth='none', methods=['GET', 'POST'], csrf=False)
    def get_calllog(self, id, **kwargs):
        _logger.info(kwargs)
        uuid_token = request.httprequest.headers.get('X-CrmIService-Token')
        domain = []
        user = request.env['res.users'].sudo().search([('uuid_token', '=', uuid_token)])
        if id is not None:
            domain.append(('log_id', '=', id))
        if user:
            log = request.env['voip.call'].with_user(user).search(domain)
            log_list = [{
                "id": rec.log_id,
                "userid": None,
                "customerid": "0032000001DrFDSAA3",
                "customertype": rec.partner_id.type if rec.partner_id else '',
                "subject": "PBXware call",
                "phonenumber": rec.phone_number,
                "direction": rec.direction,
                "duration": 0,
                "starttime": rec.start_date,
                "status": rec.state,
                "description": "",
                "asteriskcallid1": "",
                "asteriskcallid2": "",
                "recordname": "",
                "recorddesc": ""
            } for rec in log]
            response = Response(json.dumps(log_list), status=200, content_type='application/json')
            return response
        else:
            response = Response(json.dumps({"error": "Invalid or missing authorization token"}), status=401,
                                content_type='application/json')
            return response

