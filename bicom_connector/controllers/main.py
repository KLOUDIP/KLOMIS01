# -*- coding: utf-8 -*-
import pytz
import json
import logging
from datetime import datetime
from markupsafe import Markup

from odoo import http, _, fields
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

STATUS = {"ANSWERED": 'answered', "UNANSWERED": 'unanswered', "BUSY": 'aborted', "UNAVAILABLE": 'terminated', "INPROGRESS": 'ongoing', 'REJECTED': 'rejected'}
RESPONSE_STATUS = {"answered": 'ANSWERED', "unanswered": 'UNANSWERED', "aborted": 'BUSY', "terminated": 'UNAVAILABLE', "ongoing": 'INPROGRESS', 'rejected': 'UNAVAILABLE'}

class BiComController(http.Controller):

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

    @http.route(['/customers', '/customers/search'], type='http', auth='none', methods=['GET'], csrf=False)
    def get_customers(self, **kwargs):
        uuid_token = request.httprequest.headers.get('X-CrmIService-Token')
        domain = []
        user = request.env['res.users'].sudo().search([('uuid_token', '=', uuid_token)])
        phonenumber = kwargs.get('phonenumber', '').strip()
        if phonenumber != '':
            domain.append(('phone_sanitized', '!=', False))
        if user:
            customers = request.env['res.partner'].sudo().with_user(user).search(domain).filtered(lambda x: x.phone_sanitized[-8:] == phonenumber[-8:])
            if not customers:
               customers = request.env['res.partner'].sudo().create({'name': phonenumber, 'phone': phonenumber})
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
                "subject": rec.display_name,
                "phonenumber": rec.phone_number,
                "direction": rec.direction,
                "duration": 0,
                "starttime": int(rec.start_date.timestamp()) if rec.start_date else '',
                "status": RESPONSE_STATUS[rec.status] if rec.status != False else 'UNAVAILABLE',
                "description": rec.display_name,
                "asteriskcallid1": rec.asteriskcallid_one,
                "asteriskcallid2": rec.asteriskcallid_two,
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
                'state': STATUS[json_data.get('status', 'rejected')],
                'activity_name': json_data.get('subject', ''),
                'user_id': user.id,
                'start_date': fields.Datetime.now(),
                'asteriskcallid_one': json_data.get('asteriskcallid1', False),
                'asteriskcallid_two': json_data.get('asteriskcallid2', False),
            })
            if call_rec:
                local_tz = pytz.timezone('Asia/Colombo')
                utc_dt = pytz.utc.localize(call_rec.start_date)
                user_dt = utc_dt.astimezone(local_tz)
                tz_datetime = datetime.strftime(user_dt, "%Y-%m-%d %H:%M:%S")

                body = Markup(f"""
                        Subject - {call_rec.activity_name} <br/>
                        Description - {call_rec.display_name} <br/>
                        Direction - {call_rec.direction} <br/>
                        Start Time - {tz_datetime} <br/>
                        Phone Number - {call_rec.phone_number} <br/>
                        Responsible User - {call_rec.user_id.name}
                """)
                call_rec.write({'log_note': body})
                data = {
                    "id": call_rec.id,
                    "status": RESPONSE_STATUS[call_rec.state] if call_rec.state != False else 'UNAVAILABLE',
                    "customerid": call_rec.partner_id.id,
                    "customertype": "Contact",
                    "phonenumber": call_rec.partner_id.phone_sanitized,
                    "direction": "OUTBOUND" if call_rec.direction == 'outgoing' else "INBOUND",
                    "duration": call_rec.duration,
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