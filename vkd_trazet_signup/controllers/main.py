import logging
import re

import requests

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

REFERENCE_DATA_LIMIT = 300
REQUIRED_FIELDS = [
    'email', 'name', 'phone', 'password', 'repeatPassword',
    'countryId', 'timezoneId', 'organizationName',
]
PHONE_PATTERN = re.compile(r'^\+[1-9]\d{6,14}$')


class TrazetSignupController(http.Controller):

    def _get_config(self):
        icp = request.env['ir.config_parameter'].sudo()
        return {
            'api_url': icp.get_param('vkd_trazet_signup.api_url', 'https://dev.api.trazet.com/api'),
            'redirect_url': icp.get_param('vkd_trazet_signup.redirect_url', 'https://dev.trazet.com/login'),
            'domain': icp.get_param('vkd_trazet_signup.domain', 'dev.trazet.com'),
        }

    def _fetch_reference_data(self, api_url, path):
        try:
            response = requests.get(
                f"{api_url}/shared/{path}",
                params={'page': 1, 'limit': REFERENCE_DATA_LIMIT},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            # Endpoint may wrap the list under a `data` key or return it directly.
            return data.get('data', []) if isinstance(data, dict) else data
        except (requests.exceptions.RequestException, ValueError) as e:
            _logger.error("Failed to fetch Trazet %s: %s", path, e)
            return []

    @staticmethod
    def _find_name(items, value):
        if not value:
            return ''
        value = str(value)
        for item in items:
            if str(item.get('id')) == value:
                return item.get('name') or ''
        return ''

    def _render_form(self, config, form_data=None, error=None):
        countries = self._fetch_reference_data(config['api_url'], 'countries')
        timezones = self._fetch_reference_data(config['api_url'], 'timezones')
        languages = self._fetch_reference_data(config['api_url'], 'languages')
        form_data = form_data or {}

        user = request.env.user
        email_readonly = not user._is_public() and not user.partner_id.is_trazet_user

        return request.render('vkd_trazet_signup.signup_page', {
            'countries': countries,
            'timezones': timezones,
            'languages': languages,
            'error': error,
            'form_data': form_data,
            'email_readonly': email_readonly,
            'login_url': config['redirect_url'],
            'selected_country_name': self._find_name(countries, form_data.get('countryId')),
            'selected_timezone_name': self._find_name(timezones, form_data.get('timezoneId')),
            'selected_language_name': self._find_name(languages, form_data.get('languageId')),
        })

    @http.route('/trazet-signup', type='http', auth='public', website=True, sitemap=True)
    def signup_form(self, **kwargs):
        config = self._get_config()

        user = request.env.user
        if not user._is_public():
            partner = user.partner_id
            if partner.is_trazet_user:
                # Already has a Trazet account - nothing to sign up for.
                return request.redirect(config['redirect_url'], local=False)

            return self._render_form(config, {
                'name': partner.name,
                'email': partner.email or user.login,
                'phone': partner.phone,
            })

        return self._render_form(config)

    @http.route('/trazet-signup/submit', type='http', auth='public', methods=['POST'], website=True, csrf=True)
    def signup_submit(self, **post):
        config = self._get_config()
        post = dict(post)

        missing = [f for f in REQUIRED_FIELDS if not post.get(f)]
        if missing:
            return self._render_form(config, post, f"Missing required fields: {', '.join(missing)}")

        # Trazet treats emails as case-insensitive; normalize so duplicates aren't created
        # by casing alone, and so the form redisplays the same value the API will store.
        post['email'] = post['email'].strip().lower()
        post['phone'] = post['phone'].strip()

        if not PHONE_PATTERN.match(post['phone']):
            return self._render_form(
                config, post,
                "Phone number must include the country code, e.g. +14155552671."
            )

        if post['password'] != post['repeatPassword']:
            return self._render_form(config, post, "Passwords do not match.")

        try:
            country_id = int(post['countryId'])
            timezone_id = int(post['timezoneId'])
        except (TypeError, ValueError):
            return self._render_form(config, post, "Invalid country or timezone selection.")

        payload = {
            'email': post['email'],
            'name': post['name'],
            'phone': post['phone'],
            'password': post['password'],
            'repeatPassword': post['repeatPassword'],
            'countryId': country_id,
            'timezoneId': timezone_id,
            'organizationName': post['organizationName'],
            'domain': config['domain'],
        }

        # Optional: Trazet exposes /shared/languages like /shared/countries and
        # /shared/timezones, but the sign-up payload field name for it isn't
        # confirmed yet (not shown in the saved Postman example). Sent only when
        # picked, so an unrecognized/rejected field can't block signup.
        if post.get('languageId'):
            try:
                payload['languageId'] = int(post['languageId'])
            except (TypeError, ValueError):
                pass

        try:
            response = requests.post(
                f"{config['api_url']}/v2/auth/sign-up",
                json=payload,
                timeout=15,
            )
        except requests.exceptions.RequestException as e:
            _logger.error("Trazet sign-up request failed: %s", e)
            return self._render_form(config, post, "Could not reach Trazet right now. Please try again shortly.")

        if not 200 <= response.status_code < 300:
            try:
                error_message = response.json().get('message', 'Sign-up failed.')
            except ValueError:
                error_message = 'Sign-up failed.'
            _logger.warning(
                "Trazet sign-up rejected (%s) for %s: %s",
                response.status_code, payload['email'], error_message
            )
            return self._render_form(config, post, error_message)

        _logger.info(
            "Trazet sign-up succeeded for %s (status %s), redirecting to %s",
            payload['email'], response.status_code, config['redirect_url']
        )
        return request.redirect(config['redirect_url'], local=False)