# -*- coding: utf-8 -*-
import datetime
import json
import logging
from markupsafe import Markup

from odoo import http, _
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
            customers = request.env['res.partner'].sudo().with_user(user).search(domain)
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

    @http.route(['/calllog/<string:id>'], type='http', auth='none', methods=['GET'], csrf=False)
    def get_calllog(self, id, **kwargs):
        _logger.info(kwargs)
        uuid_token = request.httprequest.headers.get('X-CrmIService-Token')
        domain = []
        user = request.env['res.users'].sudo().search([('uuid_token', '=', uuid_token)])
        if id is not None:
            domain.append(('id', '=', id))
        if user:
            log = request.env['voip.call'].with_user(user).search(domain)
            log_list = [{
                "id": rec.id,
                "userid": None,
                "customerid": rec.partner_id.id if rec.partner_id else "",
                "customertype": rec.partner_id.type if rec.partner_id else '',
                "subject": "PBXware call",
                "phonenumber": rec.phone_number,
                "direction": rec.direction,
                "duration": 0,
                "starttime": int(rec.start_date.timestamp()) if rec.start_date else '',
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

    @http.route(['/status/<string:id>'], type='http', auth='none', methods=['GET'], csrf=False)
    def get_status(self, id, **kwargs):
        _logger.info(kwargs)
        uuid_token = request.httprequest.headers.get('X-CrmIService-Token')
        domain = []
        user = request.env['res.users'].sudo().search([('uuid_token', '=', uuid_token)])
        if id is not None:
            domain.append(('id', '=', id))
        if user:
            partner = request.env['res.partner'].sudo().search(domain)
            data = {
                "id": partner.id,
                "status": "READY",
                "timestamp": 1684499266,
                "timetolive": 86400,
                "resourcetype": "CallRecord",
                "resourceid": "23487cdc093e810a01ff0"
            }
            response = Response(json.dumps(data), status=200, content_type='application/json')
            return response
        else:
            response = Response(json.dumps({"error": "Invalid or missing authorization token"}), status=401,
                                content_type='application/json')
            return response

    @http.route(['/calllog'], type='http', auth='none', methods=['POST'], csrf=False)
    def create_calllog(self, **kwargs):
        """
            Create calllog with bicom request data
        """
        _logger.info("---------------------------------------")
        json_data = json.loads(request.httprequest.data)
        _logger.info(json_data)
        uuid_token = request.httprequest.headers.get('X-CrmIService-Token')
        user = request.env['res.users'].sudo().search([('uuid_token', '=', uuid_token)])
        Call = request.env['voip.call']
        if user:
            if bool(json_data) == False:
                data = {
                    "id": 0000,
                    "status": "READY",
                    "timestamp": "",
                    "timetolive": 86400,
                    "resourcetype": None,
                    "resourceid": None
                }
                response = Response(json.dumps(data), status=200, content_type='application/json')
                return response
            call_rec = Call.sudo().create({
                'display_name': json_data.get('description', ''),
                'phone_number': json_data.get('phonenumber', ''),
                'direction': 'incoming' if json_data.get('direction', '') == 'INBOUND' else 'outgoing',
                'partner_id': int(json_data.get('customerid', False)) if json_data.get('customerid', False) else False,
                'state': 'calling',
                'activity_name': json_data.get('subject', ''),
                'user_id': user.id,
                'start_date': datetime.datetime.now(),
                'asteriskcallid_one': json_data.get('asteriskcallid1', False),
                'asteriskcallid_two': json_data.get('asteriskcallid2', False),
            })
            if call_rec:
                body = Markup(f"""
                        Subject - {call_rec.activity_name} <br/>
                        Description - {call_rec.display_name} <br/>
                        Direction - {call_rec.direction} <br/>
                        Start Time - {call_rec.start_date} <br/>
                        Responsible User - {call_rec.user_id.name}
                """)
                contact = call_rec.partner_id

                contact.with_user(user).message_post(body=body, message_type='notification', subtype_xmlid="mail.mt_comment")
                data = {
                    "id": call_rec.id,
                    "status": "ANSWERED",
                    "customerid": call_rec.partner_id.id,
                    "customertype": "Contact",
                    "phonenumber": call_rec.partner_id.phone_sanitized,
                    "direction": "OUTBOUND" if call_rec.direction == 'outgoing' else "INBOUND",
                    "duration": 15,
                    "subject": call_rec.display_name,
                    "timestamp": int(call_rec.start_date.timestamp()),
                    "timetolive": 86400,
                    "resourcetype": None,
                    "resourceid": None
                }
                response = Response(json.dumps(data), status=200, content_type='application/json')
                return response
            else:
                response = Response(json.dumps({"error": "Invalid parameters/json in body or query"}), status=400, content_type='application/json')
                return response
        else:
            response = Response(json.dumps({"error": "Invalid or missing authorization token"}), status=401,
                                content_type='application/json')
            return response

    @http.route(['/recording'], type='http', auth='none', methods=['POST'], csrf=False)
    def create_recording_log(self, **kwargs):
        json_data = json.loads(request.httprequest.data)
        uuid_token = request.httprequest.headers.get('X-CrmIService-Token')
        user = request.env['res.users'].sudo().search([('uuid_token', '=', uuid_token)])
        Call = request.env['voip.call']
        if user:
            if bool(json_data) == False:
                response = Response({"error": "Invalid parameters/json in body"}, status=400, content_type='application/json')
                return response
            call_rec = Call.sudo().browse(int(json_data['calllogid']))
            if call_rec:
                call_rec.partner_id.with_user(user).message_post(body=Markup(f"<a href={json_data['recordingurl']}>Recording</a>"), message_type='comment', subject=json_data['description'])
                response = Response(json.dumps({"message": "Success"}), status=200, content_type='application/json')
                return response
            else:
                response = Response(json.dumps({"error": f"Couldn't find Call log with provided {json_data['calllogid']}"}), status=404,
                                    content_type='application/json')
                return response
        else:
            response = Response(json.dumps({"error": "Invalid or missing authorization token"}), status=401,
                                content_type='application/json')
            return response