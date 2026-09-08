# -*- coding: utf-8 -*-
import json
import logging

import requests

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

FIOS_ERR_OK = 0
FIOS_ERR_INVALID_SESSION = 1
FIOS_ERR_INVALID_INPUT = 4
FIOS_ERR_REQUEST_FAILED = 5
FIOS_ERR_ACCESS_DENIED = 7
FIOS_ERR_INVALID_CREDENTIALS = 8

FIOS_RETRYABLE_ERRORS = {FIOS_ERR_REQUEST_FAILED}


class FiosApiError(Exception):

    def __init__(self, code, svc, message=None, reason=None):
        self.code = code
        self.svc = svc
        desc = message or self._describe(code)
        if reason:
            desc = f"{desc} ({reason})"
        self.message = f"[{code}] {desc}"
        super().__init__(f"FIOS error on '{svc}': {self.message}")

    @staticmethod
    def _describe(code):
        return {
            1: 'Invalid session',
            2: 'Invalid service name',
            3: 'Invalid result',
            4: 'Invalid input',
            5: 'Error performing request',
            6: 'Unknown error',
            7: 'Access denied',
            8: 'Invalid user name or password',
            9: 'Authorization server unavailable',
            10: 'Reached limit of concurrent requests',
            11: 'Password reset error',
            14: 'Billing error',
            1001: 'No message for the selected interval',
            1002: 'Item with such unique property already exists, or creation denied by billing',
            1003: 'Only one request of given type is allowed at the moment',
            1004: 'Limit of messages has been reached',
            1005: 'Execution time exceeded the limit',
            1011: 'Your IP has changed or session has expired',
        }.get(code, 'Unrecognized FIOS error code')

    @property
    def is_retryable(self):
        return self.code in FIOS_RETRYABLE_ERRORS


class FiosApiClient(models.AbstractModel):
    _name = 'fios.api.client'
    _description = 'FIOS API Client'

    _DEFAULT_TIMEOUT = 30

    @api.model
    def _default_tier(self):
        tier = self.env['fios.service.tier'].search([], order='sequence, id', limit=1)
        if not tier:
            raise UserError(_("No FIOS service tier is configured."))
        return tier

    @api.model
    def _resolve_tier(self, tier):
        return tier or self._default_tier()

    @api.model
    def _get_config(self, tier):
        if not tier.base_url or not tier.token:
            raise UserError(_("FIOS tier '%s' is not configured (base_url / token missing).") % tier.name)
        return {
            'base_url': tier.base_url.rstrip('/'),
            'token': tier.token,
            'creator_id': tier.creator_id,
        }

    @api.model
    def get_creator_id(self, tier=None):
        tier = self._resolve_tier(tier)
        if not tier.creator_id:
            raise UserError(_("FIOS creator_id is not configured for tier '%s'.") % tier.name)
        return int(tier.creator_id)

    @api.model
    def _login(self, tier):
        config = self._get_config(tier)
        url = f"{config['base_url']}/wialon/ajax.html"
        params = {'token': config['token'], 'fl': 1}

        _logger.info("FIOS: logging in to obtain a new SID for tier %s", tier.name)
        resp = requests.get(
            url,
            params={'svc': 'token/login', 'params': json.dumps(params)},
            timeout=self._DEFAULT_TIMEOUT,
        )
        data = resp.json()
        if not isinstance(data, dict) or 'eid' not in data:
            code = data.get('error') if isinstance(data, dict) else None
            raise FiosApiError(code or FIOS_ERR_ACCESS_DENIED, 'token/login',
                               'Login did not return a session id')

        # Retire any previous active session for this tier, store the new one.
        self.env['fios.session'].get_active_session(tier).invalidate()
        session = self.env['fios.session'].sudo().create({
            'sid': data['eid'],
            'tier_id': tier.id,
            'auth_user': data.get('au'),
            'login_time': fields.Datetime.now(),
            'last_activity': fields.Datetime.now(),
            'active': True,
        })
        _logger.info("FIOS: obtained new SID for tier %s (user %s)", tier.name, data.get('au'))
        return session

    @api.model
    def _get_sid(self, tier):
        session = self.env['fios.session'].get_active_session(tier)
        if not session:
            session = self._login(tier)
        return session.sid

    @api.model
    def call(self, svc, params, tier=None, retry_on_expiry=True):
        tier = self._resolve_tier(tier)
        config = self._get_config(tier)
        sid = self._get_sid(tier)
        url = f"{config['base_url']}/wialon/ajax.html"

        try:
            resp = requests.post(
                url,
                data={'svc': svc, 'params': json.dumps(params), 'sid': sid},
                timeout=self._DEFAULT_TIMEOUT,
            )
        except requests.exceptions.RequestException as e:
            _logger.error("FIOS transport error on '%s': %s", svc, e)
            raise UserError(_("Failed to reach FIOS API: %s") % e)

        try:
            data = resp.json()
        except ValueError:
            raise UserError(_("FIOS returned a non-JSON response for '%s'.") % svc)

        # Wialon signals logical failure with {"error": <code>} even on HTTP 200.
        if isinstance(data, dict) and data.get('error', FIOS_ERR_OK) != FIOS_ERR_OK:
            code = data['error']
            if code == FIOS_ERR_INVALID_SESSION and retry_on_expiry:
                _logger.info("FIOS: session expired on '%s', re-logging in", svc)
                self.env['fios.session'].get_active_session(tier).invalidate()
                self._login(tier)
                return self.call(svc, params, tier=tier, retry_on_expiry=False)
            # `reason` carries a human-readable detail on many errors (e.g. 5).
            reason = data.get('reason') if isinstance(data, dict) else None
            _logger.warning("FIOS error on '%s': full response=%s", svc, data)
            raise FiosApiError(code, svc, reason=reason)

        # Refresh activity so the keep-alive cron knows the session is live.
        self.env['fios.session'].get_active_session(tier).touch()
        return data

    @api.model
    def cron_fios_keepalive(self):
        if self.env['ir.config_parameter'].sudo().get_param(
                'vkd_fios_api.keepalive_active', '1') not in ('1', 'True', 'true'):
            return

        # Ping each active tier session (one live SID per token). One bad session
        # must not abort the whole cron.
        for session in self.env['fios.session'].search([('active', '=', True)]):
            # Stale session from before tiers existed (no tier) - drop it.
            if not session.tier_id:
                session.invalidate()
                continue
            try:
                config = self._get_config(session.tier_id)
                requests.get(
                    f"{config['base_url']}/avl_evts",
                    params={'sid': session.sid},
                    timeout=15,
                )
                session.touch()
                _logger.debug("FIOS: keep-alive ping sent for tier %s (SID %s)",
                              session.tier_id.name, session.sid)
            except Exception as e:
                _logger.warning("FIOS: keep-alive failed for tier %s, invalidating: %s",
                                session.tier_id.name, e)
                session.invalidate()