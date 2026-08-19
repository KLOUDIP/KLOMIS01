# -*- coding: utf-8 -*-
import logging
import secrets
import string

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# FIOS service registry (per the FIOS Services Params sheet). Two kinds:
#   - quantity : the subscribed qty becomes the limit  -> costTable "<n>:0;-1"
#   - feature  : enable/disable only  -> enable costTable "", disable "-1"
# `default` is the value applied at account creation (0 = feature disabled).
FIOS_SERVICE_META = {
    'avl_unit':            {'label': 'Units / Devices', 'type': 2, 'feature': False, 'default': 0},
    'storage_user':        {'label': 'Users',           'type': 2, 'feature': False, 'default': 2},
    'zones_library':       {'label': 'Geofences',       'type': 2, 'feature': False, 'default': 5},
    'own_google_service':  {'label': 'Google Maps',     'type': 1, 'feature': True,  'default': 0},
    'ecodriving':          {'label': 'Ecodriving',      'type': 1, 'feature': True,  'default': 0},
    'avl_retranslator':    {'label': 'Data Streaming',  'type': 2, 'feature': True,  'default': 0},
}


def fios_service_type(name):
    return FIOS_SERVICE_META.get(name, {}).get('type', 2)


def fios_cost_table(name, value):
    """Build the costTable for a service given its computed value/quantity.
    Feature services: enable ("") when value>0, else disable ("-1").
    Quantity services: "<value>:0;-1"."""
    meta = FIOS_SERVICE_META.get(name, {'feature': False})
    value = int(value or 0)
    if meta['feature']:
        return '' if value > 0 else '-1'
    return '%s:0;-1' % value


# Account flags: 32 = block-by-days (days counter) billing mode.
DEFAULT_ACCOUNT_FLAGS = 32
USER_FLAG_CREATE_ITEMS = 4


class FiosProvisioning(models.AbstractModel):
    """Orchestrates the FIOS customer-account provisioning sequence.

    Sequence (stop on first failure):
        1. core/create_user       -> partner.fios_user_id
        2. core/create_resource   -> partner.fios_resource_id / fios_account_item_id
        3. account/create_account -> account created on the resource

    The per-step state on the partner (fios_provision_state) makes the flow
    idempotent and resumable: re-running skips already-completed steps.
    """
    _name = 'fios.provisioning'
    _description = 'FIOS Provisioning Orchestration'

    SPECIAL_CHARS = "!@#$%^&*-_"

    @api.model
    def validate_password(self, password, username):
        if not password or len(password) < 8:
            return _("Password must be at least 8 characters long.")
        if not any(c.islower() for c in password):
            return _("Password must contain at least one lowercase letter.")
        if not any(c.isupper() for c in password):
            return _("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in password):
            return _("Password must contain at least one number.")
        if not any(c in self.SPECIAL_CHARS for c in password):
            return _("Password must contain at least one special character (%s).") % self.SPECIAL_CHARS
        if password == username:
            return _("Password must be different from the username.")
        return None

    @api.model
    def _generate_password(self, username):
        alphabet = string.ascii_letters + string.digits + self.SPECIAL_CHARS
        while True:
            pwd = ''.join(secrets.choice(alphabet) for _ in range(14))
            if not self.validate_password(pwd, username):
                return pwd

    @api.model
    def _fios_username(self, partner):
        user = partner.user_ids[:1]
        return (user.login if user else partner.email) or ("partner_%s" % partner.id)

    @api.model
    def _resolve_tier(self, partner, tier=None):
        tier = tier or partner.fios_tier_id
        if not tier:
            tier = self.env['fios.api.client']._default_tier()
        return tier

    # Ordered provisioning states; used to make each step resumable.
    _STATE_ORDER = ['not_started', 'user_created', 'user_flags_set', 'resource_created',
                    'account_created', 'active']

    def _reached(self, partner, state):
        current = partner.fios_provision_state
        if current not in self._STATE_ORDER:
            return False
        return self._STATE_ORDER.index(current) >= self._STATE_ORDER.index(state)

    def _build_default_services_batch(self, item_id):
        # Only set the quantity services (units/users/geofences) at creation.
        # Feature services (Google Maps, Ecodriving, Data Streaming) are left at
        # the plan default (disabled) and are enabled only when purchased - setting
        # them here is redundant and some (e.g. ecodriving) reject it with error 4.
        flags = int(self.env['ir.config_parameter'].sudo().get_param(
            'vkd_fios_api.account_flags', DEFAULT_ACCOUNT_FLAGS))
        subs = [{
            'svc': 'account/update_billing_service',
            'params': {
                'itemId': item_id,
                'name': name,
                'type': meta['type'],
                'intervalType': 0,
                'costTable': fios_cost_table(name, meta['default']),
            },
        } for name, meta in FIOS_SERVICE_META.items() if not meta['feature']]
        subs.append({
            'svc': 'account/update_flags',
            'params': {'itemId': item_id, 'flags': flags,
                       'blockBalance': '0', 'denyBalance': '0'},
        })
        return {'params': subs, 'flags': 0}

    @staticmethod
    def _batch_error(result):
        if not isinstance(result, list):
            return None
        for i, item in enumerate(result):
            if isinstance(item, dict) and item.get('error', 0) not in (0, None):
                return "sub-call %s -> error %s" % (i, item['error'])
        return None

    @api.model
    def provision_account(self, partner, tier=None, password=None):
        from .fios_api_client import FiosApiError
        partner = partner.sudo()
        client = self.env['fios.api.client']
        log = self.env['fios.api.log']

        tier = self._resolve_tier(partner, tier)
        if partner.fios_tier_id != tier:
            partner.fios_tier_id = tier

        if partner.fios_provision_state == 'active':
            _logger.info("FIOS: partner %s already fully provisioned, skipping", partner.id)
            return True

        if not self._valid_id(partner.fios_user_id):
            username = self._fios_username(partner)
            # Password priority: explicit arg > the customer's stashed signup
            # password > a generated compliant one.
            if not password:
                password = partner.fios_pop_pending_password()
            if password:
                pwd_error = self.validate_password(password, username)
                if pwd_error:
                    return self._fail_msg(partner, log, 'core/create_user',
                                          {'name': username, 'password': '***'}, pwd_error)
            else:
                password = self._generate_password(username)
            params = {
                'creatorId': client.get_creator_id(tier),
                'name': username,
                'password': password,
                'dataFlags': 5,
            }
            try:
                result = client.call('core/create_user', params, tier=tier)
            except FiosApiError as e:
                return self._fail(partner, log, 'core/create_user', params, e, mask_password=True)
            user_id = self._extract_id(result)
            if not user_id:
                return self._fail_msg(partner, log, 'core/create_user',
                                      {**params, 'password': '***'},
                                      _("create_user returned no id: %s") % result)
            # User created - clear the stashed password (no longer needed).
            partner.write({
                'fios_user_id': str(user_id),
                'fios_provision_state': 'user_created',
                'fios_pending_password': False,
                'fios_last_error': False,
            })
            log.log_success('core/create_user', {**params, 'password': '***'}, partner=partner,
                            response_data=result, message=_("FIOS user created"))

        if not self._reached(partner, 'user_flags_set'):
            params = {
                'userId': int(partner.fios_user_id),
                'flags': USER_FLAG_CREATE_ITEMS,
                'flagsMask': USER_FLAG_CREATE_ITEMS,
            }
            try:
                client.call('user/update_user_flags', params, tier=tier)
            except FiosApiError as e:
                return self._fail(partner, log, 'user/update_user_flags', params, e)
            partner.write({
                'fios_provision_state': 'user_flags_set',
                'fios_last_error': False,
            })
            log.log_success('user/update_user_flags', params, partner=partner,
                            message=_("FIOS user granted create-items access"))

        if not self._valid_id(partner.fios_resource_id):
            params = {
                'creatorId': int(partner.fios_user_id),
                'name': partner.commercial_company_name or partner.name,
                'skipCreatorCheck': 0,
                'dataFlags': 5,
            }
            try:
                result = client.call('core/create_resource', params, tier=tier)
            except FiosApiError as e:
                return self._fail(partner, log, 'core/create_resource', params, e)
            resource_id = self._extract_id(result)
            if not resource_id:
                return self._fail_msg(partner, log, 'core/create_resource', params,
                                      _("create_resource returned no id: %s") % result)
            resource_id = str(resource_id)
            partner.write({
                'fios_resource_id': resource_id,
                'fios_account_item_id': resource_id,
                'fios_provision_state': 'resource_created',
                'fios_last_error': False,
            })
            log.log_success('core/create_resource', params, partner=partner,
                            response_data=result, message=_("FIOS resource created"))

        if not self._reached(partner, 'account_created'):
            params = {
                'itemId': int(partner.fios_account_item_id),
                'plan': tier.plan_code,
            }
            try:
                client.call('account/create_account', params, tier=tier)
            except FiosApiError as e:
                # 1002 == account already exists on this resource; treat as done
                # so a resume after a partial failure doesn't get stuck here.
                if e.code != 1002:
                    return self._fail(partner, log, 'account/create_account', params, e)
                _logger.info("FIOS: account already exists for partner %s, continuing", partner.id)
            partner.write({
                'fios_provision_state': 'account_created',
                'fios_last_error': False,
            })
            log.log_success('account/create_account', params, partner=partner,
                            message=_("FIOS account created"))

        # Final step: set default service limits + block-by-days flag (batch).
        # No do_payment here - the billing days are set from the subscription's
        # next_invoice_date afterwards (_sync_fios_billing_date), so there is no
        # fixed trial-days call.
        if not self._reached(partner, 'active'):
            batch_params = self._build_default_services_batch(int(partner.fios_account_item_id))
            try:
                result = client.call('core/batch', batch_params, tier=tier)
            except FiosApiError as e:
                return self._fail(partner, log, 'core/batch', batch_params, e)
            batch_error = self._batch_error(result)
            if batch_error:
                return self._fail_msg(partner, log, 'core/batch', batch_params,
                                      _("Batch service setup failed: %s") % batch_error)
            partner.write({
                'fios_provision_state': 'active',
                'fios_account_enabled': True,  # account is enabled on creation
                'fios_last_sync': fields.Datetime.now(),
                'fios_last_error': False,
            })
            log.log_success('core/batch', batch_params, partner=partner,
                            response_data=result, message=_("FIOS default services set"))

        _logger.info("FIOS: partner %s fully provisioned (active)", partner.id)
        return True

    @staticmethod
    def _extract_id(result):
        if not isinstance(result, dict):
            return None
        item = result.get('item')
        if isinstance(item, dict) and item.get('id') is not None:
            return item['id']
        return result.get('id')

    @staticmethod
    def _valid_id(value):
        return bool(value) and str(value) not in ('None', 'False')

    def _fail(self, partner, log, svc, params, error, mask_password=False):
        if mask_password and 'password' in params:
            params = {**params, 'password': '***'}
        partner.write({
            'fios_provision_state': 'failed',
            'fios_last_error': error.message,
        })
        log.log_failure(svc, params, partner=partner, error_code=error.code,
                        error_msg=error.message, retryable=error.is_retryable)
        _logger.warning("FIOS: provisioning failed for partner %s at %s: %s",
                        partner.id, svc, error.message)
        return False

    def _fail_msg(self, partner, log, svc, params, message):
        partner.write({
            'fios_provision_state': 'failed',
            'fios_last_error': message,
        })
        log.log_failure(svc, params, partner=partner, error_msg=message, retryable=False)
        _logger.warning("FIOS: provisioning failed for partner %s at %s: %s",
                        partner.id, svc, message)
        return False

    @api.model
    def cron_process_fios_provisioning(self):
        """Background provisioning: for partners marked pending at purchase,
        provision the account under their tier and push limits + billing date.
        Runs off the checkout request so payment is never blocked by FIOS calls."""
        partners = self.env['res.partner'].search([
            ('fios_provision_pending', '=', True),
            ('fios_tier_id', '!=', False),
        ], limit=10)
        SaleOrder = self.env['sale.order']
        for partner in partners:
            try:
                self.provision_account(partner, tier=partner.fios_tier_id)
                partner.invalidate_recordset()
                if partner.fios_provision_state == 'active':
                    SaleOrder._fios_set_enabled(partner, True)
                    SaleOrder._sync_fios_limits(partner)
                    SaleOrder._sync_fios_billing_date(partner)
                    partner.sudo().fios_provision_pending = False
                    _logger.info("FIOS: background provisioning done for partner %s", partner.id)
                # If it failed (state 'failed'), leave pending True so the next run
                # retries; the error is recorded on the partner and in fios.api.log.
            except Exception as e:
                _logger.exception("FIOS: background provisioning error for partner %s: %s",
                                  partner.id, e)

    @api.model
    def get_account_data(self, partner):
        partner = partner.sudo()
        if not partner.fios_account_item_id:
            raise UserError(_("Partner has no FIOS account yet."))
        return self.env['fios.api.client'].call('account/get_account_data', {
            'itemId': int(partner.fios_account_item_id),
            'type': 2,
        }, tier=partner.fios_tier_id)

    @api.model
    def enable_account(self, partner, enable=True):
        partner = partner.sudo()
        if not partner.fios_account_item_id:
            raise UserError(_("Partner has no FIOS account yet."))
        return self.env['fios.api.client'].call('account/enable_account', {
            'itemId': int(partner.fios_account_item_id),
            'enable': 1 if enable else 0,
        }, tier=partner.fios_tier_id)

    @api.model
    def make_payment(self, partner, balance_update=0, days_update=0, description=''):
        partner = partner.sudo()
        if not partner.fios_account_item_id:
            raise UserError(_("Partner has no FIOS account yet."))
        return self.env['fios.api.client'].call('account/do_payment', {
            'itemId': int(partner.fios_account_item_id),
            'balanceUpdate': balance_update,
            'daysUpdate': days_update,
            'description': description,
        }, tier=partner.fios_tier_id)

    @api.model
    def update_billing_service(self, partner, name, cost_table, interval_type=0):
        partner = partner.sudo()
        if not partner.fios_account_item_id:
            raise UserError(_("Partner has no FIOS account yet."))
        return self.env['fios.api.client'].call('account/update_billing_service', {
            'itemId': int(partner.fios_account_item_id),
            'name': name,
            'type': 2,
            'intervalType': interval_type,
            'costTable': cost_table,
        }, tier=partner.fios_tier_id)

    # Services we surface on the partner (label per FIOS_SERVICE_META). Effective
    # values are read from settings.combined.services.
    TRACKED_SERVICES = [(name, meta['label']) for name, meta in FIOS_SERVICE_META.items()]

    @staticmethod
    def _format_limit(max_usage):
        if max_usage == -1:
            return 'Unlimited'
        if max_usage in (0, None):
            return '0'
        return str(max_usage)

    @api.model
    def list_accounts(self, tier):
        params = {
            'spec': {
                'itemsType': 'avl_resource',
                'propName': 'sys_name',
                'propValueMask': '*',
                'sortType': 'sys_name',
            },
            'force': 1,
            'flags': 1,  # base info (id, nm)
            'from': 0,
            'to': 0,
        }
        data = self.env['fios.api.client'].call('core/search_items', params, tier=tier)
        items = data.get('items') or []
        result = []
        for it in items:
            item_id = it.get('id')
            if not item_id:
                continue
            result.append({
                'name': it.get('nm'),
                'resource_id': str(item_id),
                'account_item_id': str(item_id),
            })
        return result

    @api.model
    def list_account_devices(self, partner):
        partner = partner.sudo()
        if not partner.fios_account_item_id:
            raise UserError(_("Partner has no FIOS account yet."))
        params = {
            'spec': {
                'itemsType': 'avl_unit',
                'propName': 'sys_billing_account_guid',
                'propValueMask': str(partner.fios_account_item_id),
                'sortType': 'sys_name',
            },
            'force': 1,
            'flags': 257,  # base + admin fields (returns uid/ph/act)
            'from': 0,
            'to': 0,
        }
        data = self.env['fios.api.client'].call('core/search_items', params,
                                                tier=partner.fios_tier_id)
        items = data.get('items') or []
        return [{
            'name': it.get('nm'),
            'imei': it.get('uid'),
            'phone': it.get('ph'),
            'active': bool(it.get('act')),
        } for it in items]

    @api.model
    def get_service_usage(self, partner):
        partner = partner.sudo()
        data = self.get_account_data(partner)
        services = ((data.get('settings') or {}).get('combined') or {}).get('services') or {}
        out = []
        for name, meta in FIOS_SERVICE_META.items():
            svc = services.get(name)
            if not svc:
                continue
            max_usage = svc.get('maxUsage')
            out.append({
                'name': name,
                'label': meta['label'],
                'feature': meta['feature'],
                'usage': svc.get('usage', 0) or 0,
                'limit': self._format_limit(max_usage),
                'enabled': (max_usage != 0) if meta['feature'] else None,
            })
        return {
            'services': out,
            'plan': data.get('plan'),
            'days': data.get('daysCounter') or 0,
            'enabled': bool(data.get('enabled')),
        }

    @api.model
    def refresh_account_status(self, partner):
        partner = partner.sudo()
        data = self.get_account_data(partner)  # raises if no account
        settings = data.get('settings') or {}
        combined = settings.get('combined') or {}
        services = combined.get('services') or {}

        lines = []
        usage_vals = []
        for key, label in self.TRACKED_SERVICES:
            svc = services.get(key)
            if not svc:
                continue
            meta = FIOS_SERVICE_META.get(key, {})
            usage = svc.get('usage', 0) or 0
            max_usage = svc.get('maxUsage')
            limit = self._format_limit(max_usage)
            lines.append("%s (%s): usage %s / limit %s" % (label, key, usage, limit))
            usage_vals.append({
                'partner_id': partner.id,
                'name': label,
                'service_code': key,
                'usage': usage,
                'limit': limit,
                'feature': meta.get('feature', False),
                'enabled': (max_usage not in (0, None)) if meta.get('feature') else False,
            })

        # Refresh the structured usage records (shown on the contact form).
        partner.fios_service_usage_ids.unlink()
        if usage_vals:
            self.env['fios.service.usage'].create(usage_vals)

        partner.write({
            'fios_account_enabled': bool(data.get('enabled')),
            'fios_days_counter': data.get('daysCounter') or 0,
            'fios_current_plan': data.get('plan') or False,
            'fios_balance': data.get('balance') or False,
            'fios_services_summary': '\n'.join(lines) or _("No tracked services found"),
            'fios_status_synced': fields.Datetime.now(),
        })
        return data