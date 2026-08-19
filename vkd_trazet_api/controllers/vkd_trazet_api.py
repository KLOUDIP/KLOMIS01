import logging
import json
import jwt
from datetime import datetime, timedelta, timezone
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class TrazetUserController(http.Controller):

    def _authenticate_request(self):
        api_key = request.httprequest.headers.get('Trazet-Auth')
        configured_key = request.env['ir.config_parameter'].sudo().get_param('tazet.jwt_secret')
        return api_key == configured_key

    def _json_response(self, data, status=200, message=None):
        if message:
            response_data = {
                'message': message,
                'statusCode': status,
                'data': data if not isinstance(data, dict) or 'error' not in data else None,
                'error': data.get('error') if isinstance(data, dict) and 'error' in data else None
            }
            # Remove None values
            response_data = {k: v for k, v in response_data.items() if v is not None}
        else:
            response_data = data

        response = request.make_response(
            json.dumps(response_data, default=str),
            headers=[('Content-Type', 'application/json')]
        )
        response.status_code = status
        return response

    @http.route('/api/trazet/create-user', type='http', auth='public', methods=['POST'], csrf=False)
    def create_user(self, **kwargs):
        """
        Create or update user in Odoo

        Required fields: name, email, phone
        Optional fields: country

        Expected JSON payload:
        {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "+1234567890",
            "country": "US"  // optional
        }
        """
        try:
            # Check authentication
            if not self._authenticate_request():
                return self._json_response(
                    {'error': 'Invalid or missing API key'},
                    status=401,
                    message='Authentication failed'
                )

            # Parse JSON data
            try:
                data = json.loads(request.httprequest.get_data(as_text=True))
            except json.JSONDecodeError:
                return self._json_response(
                    {'error': 'Invalid JSON format'},
                    status=400,
                    message='Validation failed'
                )

            # Validate required fields
            missing_fields = []
            if not data.get('email'):
                missing_fields.append('email')
            if not data.get('name'):
                missing_fields.append('name')
            if not data.get('phone'):
                missing_fields.append('phone')

            if missing_fields:
                return self._json_response(
                    {'error': f'Missing required fields: {", ".join(missing_fields)}'},
                    status=400,
                    message='Validation failed'
                )

            email = data['email']
            name = data['name']
            phone = data['phone']
            is_integrator = data.get('is_integrator', False)

            # Basic email validation
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                return self._json_response(
                    {'error': 'Invalid email format'},
                    status=400,
                    message='Validation failed'
                )

            # Check if user exists
            existing_user = request.env['res.users'].sudo().search([('login', '=', email)], limit=1)

            if existing_user:
                # Update existing user
                partner = existing_user.partner_id

                # Update partner
                partner_vals = {
                    'name': name,
                    'email': email,
                    'phone': phone,
                    'is_trazet_user': True,
                }

                # Handle optional country field
                if data.get('country'):
                    country = request.env['res.country'].sudo().search([
                        ('name', '=', data['country'])
                    ], limit=1)
                    if country:
                        partner_vals['country_id'] = country.id

                partner.sudo().write(partner_vals)

                # Update user
                existing_user.sudo().write({
                    'name': name,
                    'is_trazet_user': True,
                    'is_integrator': is_integrator,
                })

                status = 'updated'
                user_id = existing_user.id
                partner_id = partner.id
                message = 'User updated successfully'

            else:
                # Create new partner
                partner_vals = {
                    'name': name,
                    'email': email,
                    'phone': phone,
                    'customer_rank': 1,
                    'is_company': False,
                    'is_trazet_user': True,
                }

                # Handle optional country field
                if data.get('country'):
                    country = request.env['res.country'].sudo().search([
                        ('name', '=', data['country'])
                    ], limit=1)
                    if country:
                        partner_vals['country_id'] = country.id

                partner = request.env['res.partner'].sudo().create(partner_vals)

                # Create user
                portal_group = request.env.ref('base.group_portal')

                user_vals = {
                    'name': name,
                    'login': email,
                    'email': email,
                    'partner_id': partner.id,
                    'group_ids': [(6, 0, [portal_group.id])],
                    'active': True,
                    'is_trazet_user': True,
                    'is_integrator': is_integrator,
                }

                user = request.env['res.users'].sudo().create(user_vals)

                status = 'created'
                user_id = user.id
                partner_id = partner.id
                message = 'User created successfully'

            response_data = {
                'user_id': user_id,
                'partner_id': partner_id,
                'email': email,
                'name': name,
                'phone': phone,
                'status': status
            }

            return self._json_response(
                response_data,
                status=201 if status == 'created' else 200,
                message=message
            )

        except Exception as e:
            _logger.error(f"Error creating Trazet user: {str(e)}", exc_info=True)
            return self._json_response(
                {'error': 'An unexpected error occurred'},
                status=500,
                message='Internal server error'
            )


class AutoLoginController(http.Controller):

    def _json_response(self, data, status=200, message=None):
        if message:
            response_data = {
                'message': message,
                'statusCode': status,
                'data': data if not isinstance(data, dict) or 'error' not in data else None,
                'error': data.get('error') if isinstance(data, dict) and 'error' in data else None
            }
            # Remove None values
            response_data = {k: v for k, v in response_data.items() if v is not None}
        else:
            response_data = data

        response = request.make_response(
            json.dumps(response_data, default=str),
            headers=[('Content-Type', 'application/json')]
        )
        response.status_code = status
        return response

    @http.route('/web/auto-login', type='http', auth='public', methods=['GET'])
    def auto_login(self, token=None, **kw):
        try:
            # Check if token is provided
            if not token:
                return self._json_response(
                    {'error': 'Missing authentication token'},
                    status=400,
                    message='Authentication failed'
                )

            # Get JWT secret
            secret = request.env['ir.config_parameter'].sudo().get_param('tazet.jwt_secret')
            if not secret:
                return self._json_response(
                    {'error': 'JWT configuration missing'},
                    status=500,
                    message='Server configuration error'
                )

            # Decode and validate token
            try:
                payload = jwt.decode(token, secret, algorithms=['HS256'])
            except jwt.ExpiredSignatureError:
                return self._json_response(
                    {'error': 'Token has expired'},
                    status=401,
                    message='Token expired'
                )
            except jwt.InvalidTokenError as e:
                return self._json_response(
                    {'error': f'Invalid token: {str(e)}'},
                    status=401,
                    message='Invalid token'
                )

            # Get user by ID or email
            user = None
            if 'user_id' in payload:
                user = request.env['res.users'].sudo().browse(payload['user_id'])
                if not user.exists():
                    user = None

            if not user and 'email' in payload:
                user = request.env['res.users'].sudo().search([('login', '=', payload['email'])], limit=1)

            # Validate user
            if not user:
                return self._json_response(
                    {'error': 'User not found'},
                    status=404,
                    message='User not found'
                )

            if not user.active:
                return self._json_response(
                    {'error': 'User account is inactive'},
                    status=403,
                    message='Account inactive'
                )

            # Set up session (pre_login/pre_uid are plain dict keys on Session, not
            # attributes - unlike uid/login/context/session_token which are properties).
            request.session['pre_login'] = user.login
            request.session['pre_uid'] = user.id

            # Update last login
            user.sudo()._update_last_login()

            # Finalize session: sets db/login/uid/context/session_token and
            # should_rotate from the pre_login/pre_uid set above.
            request.session.finalize(request.env)

            return request.redirect(payload['redirect_url'])

        except Exception as e:
            _logger.error(f"Auto-login error: {e}", exc_info=True)
            return self._json_response(
                {'error': 'An unexpected error occurred'},
                status=500,
                message='Internal server error'
            )


class TrazetTokenController(http.Controller):

    def _authenticate_request(self):
        api_key = request.httprequest.headers.get('Trazet-Auth')
        configured_key = request.env['ir.config_parameter'].sudo().get_param('tazet.jwt_secret')
        return api_key == configured_key

    def _json_response(self, data, status=200, message=None):
        if message:
            response_data = {
                'message': message,
                'statusCode': status,
                'data': data if not isinstance(data, dict) or 'error' not in data else None,
                'error': data.get('error') if isinstance(data, dict) and 'error' in data else None
            }
            # Remove None values
            response_data = {k: v for k, v in response_data.items() if v is not None}
        else:
            response_data = data

        response = request.make_response(
            json.dumps(response_data, default=str),
            headers=[('Content-Type', 'application/json')]
        )
        response.status_code = status
        return response

    @http.route('/api/trazet/generate-token', type='http', auth='public', methods=['POST'], csrf=False)
    def generate_token(self, **kwargs):
        """
        Generate JWT token for user authentication

        Expected JSON payload:
        {
            "email": "user@example.com",
            "redirect_url": "/my/subscriptions",  // optional, defaults to "/my/subscriptions"
            "expires_in": 300                     // optional, expires in seconds, defaults to 300 (5 min)
        }

        Returns:
        {
            "message": "Token generated successfully",
            "statusCode": 200,
            "data": {
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "login_url": "https://odoo.com/web/auto-login?token=...",
                "expires_in": 300,
                "expires_at": "2024-01-01T12:05:00Z",
                "user_id": 123,
                "email": "user@example.com",
                "redirect_url": "/my/subscriptions"
            }
        }
        """
        try:
            # Check authentication
            if not self._authenticate_request():
                return self._json_response(
                    {'error': 'Invalid or missing API key'},
                    status=401,
                    message='Authentication failed'
                )

            try:
                data = json.loads(request.httprequest.get_data(as_text=True))
            except json.JSONDecodeError:
                return self._json_response(
                    {'error': 'Invalid JSON format'},
                    status=400,
                    message='Validation failed'
                )

            email = data.get('email')
            if not email:
                return self._json_response(
                    {'error': 'Missing required field: email'},
                    status=400,
                    message='Validation failed'
                )

            user = request.env['res.users'].sudo().search([('login', '=', email)], limit=1)
            if not user:
                return self._json_response(
                    {'error': 'User not found'},
                    status=404,
                    message='User not found'
                )

            if not user.active:
                return self._json_response(
                    {'error': 'User account is inactive'},
                    status=403,
                    message='Account inactive'
                )

            jwt_secret = request.env['ir.config_parameter'].sudo().get_param('tazet.jwt_secret')
            if not jwt_secret:
                return self._json_response(
                    {'error': 'JWT configuration missing'},
                    status=500,
                    message='Server configuration error'
                )

            redirect_url = data.get('redirect_url', '/my/subscriptions')
            expires_in = data.get('expires_in', 300)  # Default 5 minutes

            # Validate expires_in
            if not isinstance(expires_in, int) or expires_in <= 0 or expires_in > 86400:
                expires_in = 3600  # Default to 60 minutes if invalid

            # Generate token
            now = datetime.now(timezone.utc)
            exp_time = now + timedelta(seconds=expires_in)

            payload = {
                'user_id': user.id,
                'email': user.login,
                'name': user.name,
                'redirect_url': redirect_url,
                'exp': exp_time,
                'iat': now
            }

            token = jwt.encode(payload, jwt_secret, algorithm='HS256')

            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            login_url = f"{base_url}/web/auto-login?token={token}"

            response_data = {
                'token': token,
                'login_url': login_url,
                'expires_in': expires_in,
                'expires_at': exp_time.isoformat(),
                'user_id': user.id,
                'email': user.login,
                'name': user.name,
                'redirect_url': redirect_url
            }

            return self._json_response(
                response_data,
                status=200,
                message='Token generated successfully'
            )

        except Exception as e:
            _logger.error(f"Error generating token: {str(e)}", exc_info=True)
            return self._json_response(
                {'error': 'An unexpected error occurred'},
                status=500,
                message='Internal server error'
            )

    @http.route('/api/trazet/validate-token', type='http', auth='public', methods=['POST'], csrf=False)
    def validate_token(self, **kwargs):
        """
        Validate JWT token without logging in

        Expected JSON payload:
        {
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        }

        Returns:
        {
            "message": "Token is valid",
            "statusCode": 200,
            "data": {
                "valid": true,
                "user_id": 123,
                "email": "user@example.com",
                "name": "John Doe",
                "expires_in": 240,
                "expires_at": "2024-01-01T12:05:00Z",
                "redirect_url": "/my/subscriptions"
            }
        }
        """
        try:
            try:
                data = json.loads(request.httprequest.get_data(as_text=True))
            except json.JSONDecodeError:
                return self._json_response(
                    {'error': 'Invalid JSON format'},
                    status=400,
                    message='Validation failed'
                )

            token = data.get('token')
            if not token:
                return self._json_response(
                    {'error': 'Missing token in request body'},
                    status=400,
                    message='Validation failed'
                )

            jwt_secret = request.env['ir.config_parameter'].sudo().get_param('tazet.jwt_secret')
            if not jwt_secret:
                return self._json_response(
                    {'error': 'JWT configuration missing'},
                    status=500,
                    message='Server configuration error'
                )

            try:
                payload = jwt.decode(token, jwt_secret, algorithms=['HS256'])
            except jwt.ExpiredSignatureError:
                return self._json_response(
                    {'error': 'Token has expired', 'valid': False},
                    status=401,
                    message='Token expired'
                )
            except jwt.InvalidTokenError as e:
                return self._json_response(
                    {'error': f'Invalid token: {str(e)}', 'valid': False},
                    status=401,
                    message='Invalid token'
                )

            user = None
            if 'user_id' in payload:
                user = request.env['res.users'].sudo().browse(payload['user_id'])
                if not user.exists():
                    user = None

            if not user and 'email' in payload:
                user = request.env['res.users'].sudo().search([('login', '=', payload['email'])], limit=1)

            if not user:
                return self._json_response(
                    {'error': 'User not found', 'valid': False},
                    status=404,
                    message='User not found'
                )

            if not user.active:
                return self._json_response(
                    {'error': 'User account is inactive', 'valid': False},
                    status=403,
                    message='Account inactive'
                )

            exp_timestamp = payload.get('exp')
            expires_in = 0
            expires_at = None
            if exp_timestamp:
                if isinstance(exp_timestamp, datetime):
                    exp_datetime = exp_timestamp
                else:
                    exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)

                now = datetime.now(timezone.utc)
                expires_in = max(0, int((exp_datetime - now).total_seconds()))
                expires_at = exp_datetime.isoformat()

            response_data = {
                'valid': True,
                'user_id': user.id,
                'email': user.login,
                'name': user.name,
                'expires_in': expires_in,
                'expires_at': expires_at,
                'redirect_url': payload.get('redirect_url', '/my/subscriptions')
            }

            return self._json_response(
                response_data,
                status=200,
                message='Token is valid'
            )

        except Exception as e:
            _logger.error(f"Error validating token: {str(e)}", exc_info=True)
            return self._json_response(
                {'error': 'An unexpected error occurred', 'valid': False},
                status=500,
                message='Internal server error'
            )

    @http.route('/api/trazet/refresh-token', type='http', auth='public', methods=['POST'], csrf=False)
    def refresh_token(self, **kwargs):
        """
        Refresh/extend JWT token expiry

        Expected JSON payload:
        {
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "expires_in": 600  // optional, new expiry time in seconds
        }

        Returns new token with extended expiry
        """
        try:
            if not self._authenticate_request():
                return self._json_response(
                    {'error': 'Invalid or missing API key'},
                    status=401,
                    message='Authentication failed'
                )

            try:
                data = json.loads(request.httprequest.get_data(as_text=True))
            except json.JSONDecodeError:
                return self._json_response(
                    {'error': 'Invalid JSON format'},
                    status=400,
                    message='Validation failed'
                )

            token = data.get('token')
            if not token:
                return self._json_response(
                    {'error': 'Missing token in request body'},
                    status=400,
                    message='Validation failed'
                )

            jwt_secret = request.env['ir.config_parameter'].sudo().get_param('tazet.jwt_secret')
            if not jwt_secret:
                return self._json_response(
                    {'error': 'JWT configuration missing'},
                    status=500,
                    message='Server configuration error'
                )

            try:
                payload = jwt.decode(token, jwt_secret, algorithms=['HS256'], options={"verify_exp": False})
            except jwt.InvalidTokenError as e:
                return self._json_response(
                    {'error': f'Invalid token: {str(e)}'},
                    status=401,
                    message='Invalid token'
                )

            user = request.env['res.users'].sudo().browse(payload.get('user_id'))
            if not user.exists() or not user.active:
                return self._json_response(
                    {'error': 'User not found or inactive'},
                    status=404,
                    message='User not found'
                )

            expires_in = data.get('expires_in', 300)  # Default 5 minutes
            if not isinstance(expires_in, int) or expires_in <= 0 or expires_in > 3600:
                expires_in = 300

            now = datetime.now(timezone.utc)
            exp_time = now + timedelta(seconds=expires_in)

            new_payload = {
                'user_id': user.id,
                'email': user.login,
                'name': user.name,
                'redirect_url': payload.get('redirect_url', '/my/subscriptions'),
                'exp': exp_time,
                'iat': now
            }

            new_token = jwt.encode(new_payload, jwt_secret, algorithm='HS256')

            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            login_url = f"{base_url}/web/auto-login?token={new_token}"

            response_data = {
                'token': new_token,
                'login_url': login_url,
                'expires_in': expires_in,
                'expires_at': exp_time.isoformat(),
                'user_id': user.id,
                'email': user.login,
                'name': user.name,
                'redirect_url': payload.get('redirect_url', '/my/subscriptions')
            }

            return self._json_response(
                response_data,
                status=200,
                message='Token refreshed successfully'
            )

        except Exception as e:
            _logger.error(f"Error refreshing token: {str(e)}", exc_info=True)
            return self._json_response(
                {'error': 'An unexpected error occurred'},
                status=500,
                message='Internal server error'
            )