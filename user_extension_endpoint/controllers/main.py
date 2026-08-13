# -*- coding: utf-8 -*-

import json
import logging
import requests

import xmlrpc.client

from odoo import http, SUPERUSER_ID
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class UserExtensionController(http.Controller):

    @http.route(
        '/get/user/extension',
        type='jsonrpc',
        auth="public",
        methods=['GET', 'POST'],
        csrf=False
    )
    def get_user_extension(self, **kwargs):
        """
        Authenticate with odoo server and get user extension
        """
        # ==============================================
        # NESTED
        # ==============================================
        def _authentication_with_api_key():
            """
            @nested: get user if authentication type is api_key
            """
            common = xmlrpc.client.ServerProxy(f'{base_url}/xmlrpc/2/common')
            users = common.authenticate(db_name, data.get('username'), data.get('password'), {})
            if users:
                user_id = request.env['res.users'].with_user(SUPERUSER_ID).browse(users)
                stat, code = {'user_name': user_id.partner_id.name}, 200
            else:
                stat, code = {'error': 'Invalid username or api_key'}, 400
            return stat, code

        def _authentication_with_password():
            """
            @nested: get user if authentication type is password
            """
            # Create a session and get session info
            payload = {
                "params": {
                    'db': db_name,
                    'login': data.get('username'),
                    'password': data.get('password')
                },
            }
            headers = {
                "Content-Type": "application/json",
            }
            session_details = requests.get(
                url=base_url + '/web/session/authenticate',
                data=json.dumps(payload),
                headers=headers)
            # Check session status
            if session_details.status_code == 200:
                if session_details.json().get('error', False):
                    stat, code = {'error': session_details.json()['error']['data']['arguments'][0]}, 400
                else:
                    # Extract the user from session
                    user_id = session_details.json().get('result').get('user_id')
                    if user_id:
                        user_id = request.env['res.users'].with_user(SUPERUSER_ID).browse(user_id)
                    stat, code = {'user_name': user_id.partner_id.name}, 200
                    # Logout from the created session
                    request.session.logout()
            else:
                stat, code = {'error': 'Unknown error occurred'}, 400
            return stat, code

        # ===========================================================
        # MAIN
        # ===========================================================
        try:
            data = request.httprequest.data
            if data:
                # Convert data to a dictionary
                data = json.loads(data)
                _logger.info('Data has been successfully received')
                db_name = 'kloudip-klomis01-klostag-17-7-12389274'  # TODO: change the database name
                base_url = request.env.user.get_base_url()
                # Check the payload data validity
                payload_data_valid = data.get('auth_type') in ['password', 'api_key'] and data.get('username', False) and data.get('password', False)
                if payload_data_valid:
                    if data['auth_type'] == 'password':
                        _logger.info("Authenticating with odoo server using password")
                        status, status_code = _authentication_with_password()
                    else:
                        _logger.info("Authenticating with odoo server using api_key")
                        status, status_code = _authentication_with_api_key()
                else:
                    status, status_code = {'error': 'Ensure that the username, password, and auth_type are provided. '
                                                    'Options for the auth_type include "password" or "api_key".'}, 400
            else:
                status, status_code = {'error': 'The JSON body provided is not valid'}, 400
        except Exception as e:
            status, status_code = {'error': e}, 400
        _logger.info(status)
        # return Response(
        #     json.dumps(status),
        #     status=status_code,
        #     content_type='application/json'
        # )
        return json.dumps(status)
