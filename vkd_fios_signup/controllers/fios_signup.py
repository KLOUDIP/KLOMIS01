# -*- coding: utf-8 -*-
import logging
import re
import secrets
import time
from urllib.parse import quote

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ['name', 'email', 'phone', 'organizationName', 'password', 'repeatPassword']
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
# Where the visitor continues their purchase after signing up / logging in.
DEFAULT_CONTINUE_URL = '/shop/cart'

# OTP settings.
OTP_LENGTH = 6
OTP_TTL_SECONDS = 10 * 60          # code valid for 10 minutes
OTP_MAX_ATTEMPTS = 5               # wrong tries before the code is invalidated
OTP_RESEND_COOLDOWN_SECONDS = 60   # min seconds between sends
SESSION_KEY = 'fios_signup_otp'


def _safe_redirect(url):
    """Only allow local (same-site) redirect targets to avoid open redirects."""
    if url and url.startswith('/') and not url.startswith('//'):
        return url
    return DEFAULT_CONTINUE_URL


def _otp_enabled():
    return request.env['ir.config_parameter'].sudo().get_param(
        'vkd_fios_api.signup_otp_enabled', '1') in ('1', 'True', 'true')


def _otp_debug():
    return request.env['ir.config_parameter'].sudo().get_param(
        'vkd_fios_api.signup_otp_debug', '0') in ('1', 'True', 'true')


class FiosSignupController(http.Controller):

    def _render_form(self, form_data=None, error=None):
        return request.render('vkd_fios_signup.fios_signup_page', {
            'form_data': form_data or {},
            'error': error,
        })

    def _render_otp(self, email, error=None, info=None):
        # In debug mode, surface the current code from the (server-side) session
        # so it can be read on staging where email isn't delivered.
        debug_code = None
        if _otp_debug():
            pending = request.session.get(SESSION_KEY)
            if pending:
                debug_code = pending.get('code')
        return request.render('vkd_fios_signup.fios_signup_otp_page', {
            'email': email,
            'error': error,
            'info': info,
            'debug_code': debug_code,
        })

    def _send_otp_email(self, email, name, code):
        company = request.env.company
        subject = "Your FIOS sign-up verification code"
        body = (
            "<p>Hello %s,</p>"
            "<p>Your FIOS verification code is:</p>"
            "<p style='font-size:22px;font-weight:bold;letter-spacing:3px'>%s</p>"
            "<p>This code expires in %s minutes. If you did not request it, ignore this email.</p>"
        ) % (name or '', code, OTP_TTL_SECONDS // 60)
        try:
            mail = request.env['mail.mail'].sudo().create({
                'subject': subject,
                'body_html': body,
                'email_to': email,
                'email_from': company.email or company.name,
                'auto_delete': True,
            })
            mail.send(raise_exception=True)
            return True
        except Exception as e:
            _logger.error("FIOS signup: failed to send OTP email to %s: %s", email, e)
            return False

    def _initiate_otp(self, post, target):
        code = ''.join(secrets.choice('0123456789') for _ in range(OTP_LENGTH))
        sent = self._send_otp_email(post['email'], post.get('name'), code)
        # In debug mode (staging without mail) proceed anyway - the code is shown
        # on the verify page instead of emailed.
        if not sent and not _otp_debug():
            return False, "Could not send the verification email. Please try again shortly."
        # Session is server-side in Odoo, so the pending payload (incl. password)
        # is not exposed to the client.
        request.session[SESSION_KEY] = {
            'payload': post,
            'target': target,
            'code': code,
            'expires': time.time() + OTP_TTL_SECONDS,
            'attempts': 0,
            'last_sent': time.time(),
        }
        return True, None

    @http.route('/fios-signup', type='http', auth='public', website=True, sitemap=True)
    def signup_form(self, **kwargs):
        redirect = _safe_redirect(kwargs.get('redirect'))
        user = request.env.user
        if not user._is_public():
            partner = user.partner_id
            return self._render_form({
                'name': partner.name,
                'email': partner.email or user.login,
                'phone': partner.phone,
                'organizationName': partner.commercial_company_name or '',
                'redirect': redirect,
            })
        return self._render_form({'redirect': redirect})

    @http.route('/fios-signup/submit', type='http', auth='public', methods=['POST'],
                website=True, csrf=True)
    def signup_submit(self, **post):
        post = dict(post)
        target = _safe_redirect(post.get('redirect'))
        user = request.env.user
        is_public = user._is_public()

        missing = [f for f in REQUIRED_FIELDS if not post.get(f)]
        if missing:
            return self._render_form(post, "Missing required fields: %s" % ', '.join(missing))

        # For a logged-in visitor the account is theirs: lock the email to their login.
        if is_public:
            post['email'] = post['email'].strip().lower()
        else:
            post['email'] = user.login
        post['phone'] = post['phone'].strip()

        if not EMAIL_PATTERN.match(post['email']):
            return self._render_form(post, "Please enter a valid email address.")

        if post['password'] != post['repeatPassword']:
            return self._render_form(post, "Passwords do not match.")

        pwd_error = request.env['fios.provisioning'].sudo().validate_password(
            post['password'], post['email'])
        if pwd_error:
            return self._render_form(post, pwd_error)

        # Security: never reset an existing account's password from a public form.
        if is_public:
            existing = request.env['res.users'].sudo().search([('login', '=', post['email'])], limit=1)
            if existing:
                after_login = '/fios-signup?redirect=%s' % quote(target, safe='')
                return request.redirect('/web/login?login=%s&redirect=%s' % (
                    quote(post['email'], safe=''), quote(after_login, safe='')))

        # Email verification: for a brand-new public signup, require an OTP before
        # creating anything in Odoo or FIOS (blocks unwanted signups). Logged-in
        # users are already verified and skip this.
        if is_public and _otp_enabled():
            ok, error = self._initiate_otp(post, target)
            if not ok:
                return self._render_form(post, error)
            return self._render_otp(post['email'],
                                    info="We emailed a %s-digit code to %s." % (OTP_LENGTH, post['email']))

        return self._complete_signup(post, target, is_public)

    @http.route('/fios-signup/verify', type='http', auth='public', methods=['POST'],
                website=True, csrf=True)
    def signup_verify(self, **post):
        pending = request.session.get(SESSION_KEY)
        if not pending:
            return self._render_form(error="Your verification session expired. Please sign up again.")

        email = pending['payload']['email']
        code = (post.get('otp') or '').strip()

        if time.time() > pending['expires']:
            request.session.pop(SESSION_KEY, None)
            return self._render_form(pending['payload'],
                                     "Your code expired. Please sign up again.")

        if pending['attempts'] >= OTP_MAX_ATTEMPTS:
            request.session.pop(SESSION_KEY, None)
            return self._render_form(pending['payload'],
                                     "Too many incorrect attempts. Please sign up again.")

        if not code or code != pending['code']:
            pending['attempts'] += 1
            request.session[SESSION_KEY] = pending
            remaining = OTP_MAX_ATTEMPTS - pending['attempts']
            return self._render_otp(email,
                                    error="Incorrect code. %s attempt(s) left." % remaining)

        # Verified - complete the signup and clear the pending state.
        payload = pending['payload']
        target = pending['target']
        request.session.pop(SESSION_KEY, None)
        return self._complete_signup(payload, target, is_public=True)

    @http.route('/fios-signup/resend', type='http', auth='public', methods=['POST'],
                website=True, csrf=True)
    def signup_resend(self, **post):
        pending = request.session.get(SESSION_KEY)
        if not pending:
            return self._render_form(error="Your verification session expired. Please sign up again.")

        if time.time() - pending.get('last_sent', 0) < OTP_RESEND_COOLDOWN_SECONDS:
            return self._render_otp(pending['payload']['email'],
                                    error="Please wait a moment before requesting another code.")

        code = ''.join(secrets.choice('0123456789') for _ in range(OTP_LENGTH))
        sent = self._send_otp_email(pending['payload']['email'], pending['payload'].get('name'), code)
        if not sent and not _otp_debug():
            return self._render_otp(pending['payload']['email'],
                                    error="Could not resend the code. Please try again shortly.")
        pending.update({
            'code': code,
            'expires': time.time() + OTP_TTL_SECONDS,
            'attempts': 0,
            'last_sent': time.time(),
        })
        request.session[SESSION_KEY] = pending
        return self._render_otp(pending['payload']['email'], info="A new code has been sent.")

    def _complete_signup(self, post, target, is_public):
        # Registration creates/links the Odoo user only (state 'registered'). The
        # FIOS account is provisioned later, at purchase, under the tier of the
        # product the customer buys.
        try:
            request.env['res.users'].sudo().upsert_fios_user(
                name=post['name'],
                email=post['email'],
                phone=post['phone'],
                org_name=post['organizationName'],
                password=post['password'],
            )
        except Exception as e:
            _logger.exception("FIOS signup: failed to create/update user for %s", post['email'])
            return self._render_form(post, "Could not create the account: %s" % e)

        # A new public visitor logs in with their credentials, then continues the
        # purchase (which triggers FIOS provisioning). Logged-in users continue directly.
        if is_public:
            return request.redirect('/web/login?login=%s&redirect=%s' % (
                quote(post['email'], safe=''), quote(target, safe='')))
        return request.redirect(target)
