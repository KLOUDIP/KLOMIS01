# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# FIOS cuts access when the block-by-days counter reaches this value.
FIOS_BLOCK_DAYS_THRESHOLD = -1


def _fios_fernet(env):
    from cryptography.fernet import Fernet
    icp = env['ir.config_parameter'].sudo()
    key = icp.get_param('vkd_fios_api.pwd_secret')
    if not key:
        key = Fernet.generate_key().decode()
        icp.set_param('vkd_fios_api.pwd_secret', key)
    return Fernet(key.encode())


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_fios_user = fields.Boolean(
        string='Is FIOS User?',
        copy=False,
        default=False,
        help='Is this partner a FIOS-provisioned customer?',
    )

    # The single FIOS tier this customer is provisioned on. Set automatically at
    # first purchase, or manually for imported / tier-changed customers.
    fios_tier_id = fields.Many2one('fios.service.tier', string='FIOS Service Tier', copy=False)

    # Set at purchase; a cron provisions + syncs in the background so checkout
    # is never blocked by the (slow) sequence of FIOS API calls.
    fios_provision_pending = fields.Boolean(string='FIOS Provisioning Pending', copy=False, index=True)

    # The customer's chosen FIOS password, encrypted, kept only between
    # registration and the first purchase (when the FIOS user is created, then
    # cleared). System-only field.
    fios_pending_password = fields.Char(copy=False, groups='base.group_system')

    # FIOS system identifiers (returned by the provisioning calls).
    fios_user_id = fields.Char(string='FIOS User ID', copy=False, readonly=True)
    fios_resource_id = fields.Char(string='FIOS Resource ID', copy=False, readonly=True)
    fios_account_item_id = fields.Char(string='FIOS Account Item ID', copy=False, readonly=True,
                                       help='Item id of the account (equal to the resource id).')

    fios_provision_state = fields.Selection([
        ('not_started', 'Not Started'),
        ('registered', 'Registered (no FIOS account)'),
        ('user_created', 'User Created'),
        ('user_flags_set', 'User Access Set'),
        ('resource_created', 'Resource Created'),
        ('account_created', 'Account Created'),
        ('services_set', 'Default Services Set'),
        ('active', 'Active'),
        ('failed', 'Failed'),
    ], string='FIOS Provisioning', default='not_started', copy=False, index=True)

    fios_last_sync = fields.Datetime(string='FIOS Last Sync', copy=False, readonly=True)
    fios_last_error = fields.Text(string='FIOS Last Error', copy=False, readonly=True)

    # Live account status, populated by action_fios_refresh_status (read from
    # settings.combined in account/get_account_data).
    fios_account_enabled = fields.Boolean(string='FIOS Account Enabled', copy=False, readonly=True)
    fios_days_counter = fields.Integer(string='FIOS Days Left', copy=False, readonly=True,
                                       help='Days until next payment (block-by-days counter).')
    fios_current_plan = fields.Char(string='FIOS Current Plan', copy=False, readonly=True)
    fios_services_summary = fields.Text(string='FIOS Services', copy=False, readonly=True,
                                        help='Effective usage / limit per tracked FIOS service.')
    fios_status_synced = fields.Datetime(string='FIOS Status Read At', copy=False, readonly=True)

    # Human-readable access state. FIOS blocks the account when the block-by-days
    # counter drops to -1, which the raw `enabled` flag does not always reflect,
    # so both are taken into account.
    fios_account_status = fields.Selection([
        ('none', 'No Account'),
        ('active', 'Active'),
        ('blocked', 'Blocked'),
    ], string='FIOS Account Status', compute='_compute_fios_account_status',
        store=True, readonly=True)

    fios_service_usage_ids = fields.One2many('fios.service.usage', 'partner_id',
                                             string='FIOS Service Usage', copy=False)
    fios_device_ids = fields.One2many('fios.device', 'partner_id', string='FIOS Devices', copy=False)

    # --- Grace period -----------------------------------------------------
    # One 7-day grace per billing cycle. "Cycle" is identified by the
    # subscription's next_invoice_date at the moment the grace was granted:
    # once the subscription rolls to a new invoice date the button comes back.
    fios_grace_cycle_ref = fields.Date(
        string='Grace Used For Cycle', copy=False, readonly=True,
        help='The subscription invoice date the current grace period was granted against.')
    fios_grace_granted_on = fields.Datetime(string='Grace Granted On', copy=False, readonly=True)
    fios_grace_granted_by = fields.Many2one('res.users', string='Grace Granted By',
                                            copy=False, readonly=True)
    fios_grace_source = fields.Selection([
        ('backend', 'Billing Team'),
        ('portal', 'Customer Portal'),
    ], string='Grace Granted From', copy=False, readonly=True)
    fios_grace_days_granted = fields.Integer(string='Grace Days Granted', copy=False, readonly=True)
    fios_grace_expiry = fields.Date(string='Grace Ends On', copy=False, readonly=True)

    fios_grace_available = fields.Boolean(
        string='Grace Period Available', compute='_compute_fios_grace_available',
        help='True when this account is blocked and has not yet used its grace period '
             'for the current billing cycle.')

    @api.depends('fios_provision_state', 'fios_account_item_id',
                 'fios_account_enabled', 'fios_days_counter')
    def _compute_fios_account_status(self):
        for partner in self:
            if not partner.fios_account_item_id or partner.fios_provision_state != 'active':
                partner.fios_account_status = 'none'
            elif not partner.fios_account_enabled \
                    or partner.fios_days_counter <= FIOS_BLOCK_DAYS_THRESHOLD:
                partner.fios_account_status = 'blocked'
            else:
                partner.fios_account_status = 'active'

    def _fios_current_cycle_ref(self):
        """The invoice date identifying the customer's current billing cycle.

        Falls back to False when there is no live subscription - in that case the
        grace period is treated as a one-per-account allowance until a
        subscription exists.
        """
        self.ensure_one()
        # sudo: a portal user must be able to see whether their own grace period
        # is available without read access to the subscription records.
        return self.env['sale.order'].sudo()._fios_earliest_next_invoice_date(self.sudo())

    @api.depends('fios_account_status', 'fios_grace_cycle_ref', 'fios_grace_granted_on')
    def _compute_fios_grace_available(self):
        for partner in self:
            if partner.fios_account_status != 'blocked':
                partner.fios_grace_available = False
            elif not partner.fios_grace_granted_on:
                # Never used.
                partner.fios_grace_available = True
            else:
                # Used before: only available again once the subscription has
                # rolled on to a different invoice date. If either reference is
                # missing (no live subscription) it stays closed rather than
                # opening on every page load - an admin can reset it.
                cycle_ref = partner._fios_current_cycle_ref()
                partner.fios_grace_available = bool(
                    cycle_ref and partner.fios_grace_cycle_ref
                    and partner.fios_grace_cycle_ref != cycle_ref
                )

    def action_fios_refresh_devices(self):
        self.ensure_one()
        if not self.fios_account_item_id:
            raise UserError(_("This partner has no FIOS account yet."))
        try:
            devices = self.env['fios.provisioning'].list_account_devices(self)
        except Exception as e:
            raise UserError(_("Could not read FIOS devices: %s") % e)

        Device = self.env['fios.device'].sudo()
        # search + unlink rather than `self.fios_device_ids.unlink()`: the o2m is
        # the safe thing to clear only as long as nothing filters it. Going
        # through search keeps the refresh a genuine full replace.
        Device.search([('partner_id', '=', self.id)]).unlink()
        Device.create([{
            'partner_id': self.id,
            'name': d.get('name'),
            'imei': d.get('imei'),
            'phone': d.get('phone'),
            'device_active': d.get('active'),
        } for d in devices])

        activated = sum(1 for d in devices if d.get('active'))
        deactivated = len(devices) - activated
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('FIOS Devices'),
                'message': _('%(total)s device(s) loaded - %(on)s activated, %(off)s deactivated.')
                % {'total': len(devices), 'on': activated, 'off': deactivated},
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def fios_store_pending_password(self, raw):
        self.ensure_one()
        if not raw:
            return
        try:
            token = _fios_fernet(self.env).encrypt(raw.encode()).decode()
            self.sudo().fios_pending_password = token
        except Exception as e:
            _logger.error("FIOS: could not store pending password for partner %s: %s", self.id, e)

    def fios_pop_pending_password(self):
        self.ensure_one()
        enc = self.sudo().fios_pending_password
        if not enc:
            return None
        try:
            return _fios_fernet(self.env).decrypt(enc.encode()).decode()
        except Exception as e:
            _logger.error("FIOS: could not decrypt pending password for partner %s: %s", self.id, e)
            return None

    def action_fios_provision(self):
        SaleOrder = self.env['sale.order']
        for partner in self:
            self.env['fios.provisioning'].provision_account(partner)
            partner.invalidate_recordset()
            # Once active, also push the current subscription limits and the
            # billing date (from next_invoice_date) - makes this a full re-sync.
            if partner.fios_provision_state == 'active':
                SaleOrder._sync_fios_limits(partner)
                SaleOrder._sync_fios_billing_date(partner)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('FIOS Provisioning'),
                'message': _('Provisioning triggered.'),
                'type': 'info',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    fios_device_diagnostic = fields.Text(string='FIOS Device Diagnostic', copy=False,
                                         readonly=True)

    def action_fios_debug_devices(self):
        """Dump what FIOS actually returns for this account's units.

        Deactivated devices missing from the list is a question about the search
        response, not about Odoo - this puts the raw response on screen (and in
        the server log) so it can be answered from evidence.
        """
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_("Only a system administrator can run the FIOS diagnostic."))
        try:
            report = self.env['fios.provisioning'].debug_device_payload(self)
        except UserError:
            raise
        except Exception as e:
            raise UserError(_("Diagnostic failed: %s") % e)
        self.sudo().fios_device_diagnostic = report
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('FIOS Device Diagnostic'),
                'message': _('Written to the FIOS tab and the server log.'),
                'type': 'info',
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def action_fios_grant_grace(self):
        """Grant this customer their once-per-cycle grace period (billing team)."""
        self.ensure_one()
        days = self.env['fios.provisioning'].grant_grace_period(self, source='backend')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('FIOS Grace Period'),
                'message': _('%s-day grace period granted. Access restored until %s.')
                % (days, self.fios_grace_expiry),
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def action_fios_reset_grace(self):
        """Admin escape hatch: clear the once-per-cycle lock.

        Needed for accounts with no live subscription (no invoice date to roll
        over on) and for correcting a grace granted in error.
        """
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_("Only a system administrator can reset a grace period."))
        self.sudo().write({
            'fios_grace_cycle_ref': False,
            'fios_grace_granted_on': False,
            'fios_grace_granted_by': False,
            'fios_grace_source': False,
            'fios_grace_days_granted': 0,
            'fios_grace_expiry': False,
        })
        self.message_post(body=_("FIOS grace period lock reset by %s.") % self.env.user.name)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('FIOS Grace Period'),
                'message': _('Grace period reset - it can be granted again this cycle.'),
                'type': 'warning',
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def action_fios_refresh_status(self):
        self.ensure_one()
        if not self.fios_account_item_id:
            raise UserError(_("This partner has no FIOS account yet."))
        try:
            self.env['fios.provisioning'].refresh_account_status(self)
        except Exception as e:
            raise UserError(_("Could not read FIOS account status: %s") % e)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('FIOS Status'),
                'message': _('Account status refreshed.'),
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }