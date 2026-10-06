# -*- coding: utf-8 -*-
import logging
import math
import time
from datetime import datetime, time as dtime, timedelta

import pytz

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

    # What the days-left counter was last synced to, and why - so the billing
    # team can see which invoice (or paid subscription period) drives it.
    fios_next_due_date = fields.Date(
        string='Days Left Run To', copy=False, readonly=True,
        help='Due date of the earliest open invoice or, when everything is paid, '
             'the end of the paid subscription period.')
    fios_days_left_source = fields.Char(
        string='Days Left Based On', copy=False, readonly=True,
        help='The invoice or subscription the days-left counter was last synced from.')
    fios_days_left_synced = fields.Datetime(string='Days Left Synced At', copy=False,
                                            readonly=True)

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

    # Set by the nightly "FIOS: Daily Sync" scheduled action after it has
    # handled this contact (whether or not FIOS answered), so one night's run
    # never picks the same contact twice.
    fios_daily_sync_at = fields.Datetime(string='Daily Sync Ran At', copy=False,
                                         readonly=True, index=True)

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
                'message': _('%(total)s device(s) loaded - %(on)s activated, %(off)s inactive.')
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

    def fios_report_devices(self):
        """Devices for the printed list, activated first then by plate.

        Kept in Python rather than sorting inside QWeb: the template stays
        readable and the ordering is testable.
        """
        self.ensure_one()
        return self.fios_device_ids.sorted(
            key=lambda device: (not device.device_active, (device.name or '').lower()))

    def action_fios_print_devices(self):
        """Print this customer's device list (Device / Plate and Status)."""
        self.ensure_one()
        return self.env.ref(
            'vkd_fios_api.action_report_fios_devices').report_action(self)

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
        """Grant this customer their once-per-cycle grace period (billing team).

        Hiding the button in the view does not stop the RPC call behind it, so
        the same rule is enforced here. FIOS Administrator implies FIOS User, so
        this covers administrators too. The portal path (vkd_fios_signup) calls
        fios.provisioning.grant_grace_period directly under sudo and is not
        affected by this check.
        """
        self.ensure_one()
        if not self.env.user.has_group('vkd_fios_api.group_fios_user'):
            raise UserError(_("Only the FIOS billing team can grant a grace period."))
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

    def _fios_unlink_account(self):
        """Detach the FIOS account from this contact (Odoo side only).

        Used to undo an import that matched a FIOS account to the wrong
        customer. Nothing is changed on FIOS itself: the account, its devices
        and its days counter stay as they are, so it can be linked to the
        right customer straight away.
        """
        self.ensure_one()
        partner = self.sudo()
        account_item_id = partner.fios_account_item_id
        if not account_item_id:
            raise UserError(_("%s has no FIOS account linked.") % partner.display_name)
        # search + unlink rather than through the o2m, same as the device refresh.
        self.env['fios.device'].sudo().search([('partner_id', '=', partner.id)]).unlink()
        self.env['fios.service.usage'].sudo().search([('partner_id', '=', partner.id)]).unlink()
        partner.write({
            'is_fios_user': False,
            'fios_tier_id': False,
            'fios_provision_pending': False,
            'fios_user_id': False,
            'fios_resource_id': False,
            'fios_account_item_id': False,
            'fios_provision_state': 'not_started',
            'fios_last_sync': False,
            'fios_last_error': False,
            'fios_account_enabled': False,
            'fios_days_counter': 0,
            'fios_current_plan': False,
            'fios_services_summary': False,
            'fios_status_synced': False,
            'fios_next_due_date': False,
            'fios_days_left_source': False,
            'fios_days_left_synced': False,
            'fios_grace_cycle_ref': False,
            'fios_grace_granted_on': False,
            'fios_grace_granted_by': False,
            'fios_grace_source': False,
            'fios_grace_days_granted': 0,
            'fios_grace_expiry': False,
            'fios_device_diagnostic': False,
        })
        partner.message_post(
            body=_("FIOS account %s unlinked from this contact by %s "
                   "(linked to the wrong customer). Nothing was changed on FIOS.")
            % (account_item_id, self.env.user.name),
            author_id=self.env.user.partner_id.id,
        )
        _logger.info("FIOS: account %s unlinked from partner %s by user %s",
                     account_item_id, partner.id, self.env.user.id)
        return account_item_id

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

    def action_fios_sync_days_left(self):
        """Billing team: recompute FIOS days left from the invoices now."""
        self.ensure_one()
        if not self.env.user.has_group('vkd_fios_api.group_fios_user'):
            raise UserError(_("Only the FIOS billing team can sync days left."))
        if self.fios_provision_state != 'active' or not self.fios_account_item_id:
            raise UserError(_("This customer has no active FIOS account."))
        res = self.env['sale.order'].sudo()._fios_push_days_left(
            self, description=_("Manual days-left sync"))
        if not res['ok']:
            raise UserError(_("Could not update FIOS days left: %s") % res['error'])
        if res['days'] is None:
            message, kind = _("No open invoice and no paid subscription period ahead - "
                              "days left left unchanged."), 'warning'
        else:
            message = _("Days left %(state)s %(days)s (runs to %(due)s - %(source)s).") % {
                'state': _('set to') if res['changed'] else _('already'),
                'days': res['days'], 'due': res['due_date'], 'source': res['source']}
            if res['re_enabled']:
                message += ' ' + _("The FIOS account was blocked and has been re-enabled.")
            kind = 'success'
            if res['changed']:
                self.message_post(body=_("FIOS days left synced manually: %s") % message)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('FIOS Days Left'),
                'message': message,
                'type': kind,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    # ------------------------------------------------------------------
    # Nightly sync (scheduled action "FIOS: Daily Sync")
    # ------------------------------------------------------------------
    def _fios_daily_sync_one(self):
        """What a user does by hand on the FIOS tab, for one contact:
        Sync Days Left, then Refresh FIOS Status, then Refresh Devices.
        Returns an error text, or None."""
        self.ensure_one()
        partner = self.sudo()
        errors = []
        try:
            with self.env.cr.savepoint():
                res = self.env['sale.order'].sudo()._fios_push_days_left(
                    partner, description=_("Daily FIOS sync"))
                if not res['ok']:
                    errors.append(_("days left: %s") % res['error'])
                elif res['changed']:
                    note = _("Daily FIOS sync: days left set to %(days)s (runs to %(due)s - "
                             "%(source)s).") % {'days': res['days'], 'due': res['due_date'],
                                                 'source': res['source']}
                    if res['re_enabled']:
                        note += ' ' + _("The blocked FIOS account was re-enabled.")
                    partner.message_post(body=note)
        except Exception as e:  # noqa: BLE001 - reported, run continues
            errors.append(_("days left: %s") % (str(e) or e.__class__.__name__))
        try:
            with self.env.cr.savepoint():
                self.env['fios.provisioning'].refresh_account_status(partner)
        except Exception as e:  # noqa: BLE001
            errors.append(_("status: %s") % (str(e) or e.__class__.__name__))
        if self.env['sale.order']._fios_icp_flag('vkd_fios_api.daily_sync_devices', '1'):
            try:
                with self.env.cr.savepoint():
                    partner.action_fios_refresh_devices()
            except Exception as e:  # noqa: BLE001
                errors.append(_("devices: %s") % (str(e) or e.__class__.__name__))
        partner.fios_daily_sync_at = fields.Datetime.now()
        return '; '.join(errors) or None

    @api.model
    def _fios_daily_sync_window(self, now_utc):
        """(start, end) of tonight's sync window in UTC, from the
        `vkd_fios_api.daily_sync_window` parameter ("HH:MM-HH:MM", local time
        of `vkd_fios_api.daily_sync_tz`). Default 00:00-02:00 Asia/Colombo."""
        icp = self.env['ir.config_parameter'].sudo()
        tz_name = icp.get_param('vkd_fios_api.daily_sync_tz', 'Asia/Colombo')
        try:
            tz = pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            tz = pytz.timezone('Asia/Colombo')
        raw = icp.get_param('vkd_fios_api.daily_sync_window', '00:00-02:00')
        try:
            start_s, end_s = [p.strip() for p in raw.split('-')]
            start_t = dtime(*map(int, start_s.split(':')))
            end_t = dtime(*map(int, end_s.split(':')))
        except Exception:  # noqa: BLE001 - bad parameter falls back to the default
            start_t, end_t = dtime(0, 0), dtime(2, 0)
        now_local = pytz.utc.localize(now_utc).astimezone(tz)

        def window(day):
            start = tz.localize(datetime.combine(day, start_t))
            end = tz.localize(datetime.combine(day, end_t))
            if end <= start:  # e.g. 23:00-01:00 crosses midnight
                end = tz.localize(datetime.combine(day + timedelta(days=1), end_t))
            return start, end

        # Yesterday's window too, for a window that crosses midnight.
        start, end = window(now_local.date())
        y_start, y_end = window(now_local.date() - timedelta(days=1))
        if y_start <= now_local < y_end:
            start, end = y_start, y_end

        def to_utc(d):
            return d.astimezone(pytz.utc).replace(tzinfo=None)
        return to_utc(start), to_utc(end)

    @api.model
    def _cron_fios_daily_sync(self):
        """Nightly: Sync Days Left + Refresh Status + Refresh Devices for every
        active FIOS account, spread over the sync window instead of all at once.

        The job starts at the beginning of the window (00:00) and works in
        small batches: each run takes its share of what is left - remaining
        accounts / remaining time slots - then schedules itself again
        `daily_sync_step_minutes` later (default 10). With the default
        00:00-02:00 window that is 12 batches, the last one around 01:50.
        Run outside the window (e.g. "Run Manually"), it simply works through
        everything that is due, within the time budget.

        An account is due when the job has not handled it in the last
        `daily_sync_min_age_hours` hours (default 12), so a night's run never
        picks the same contact twice and a failing one is not hammered.
        """
        icp = self.env['ir.config_parameter'].sudo()

        def int_param(key, default):
            try:
                return max(1, int(icp.get_param(key, default)))
            except (TypeError, ValueError):
                return default

        step_min = int_param('vkd_fios_api.daily_sync_step_minutes', 10)
        min_age_hours = int_param('vkd_fios_api.daily_sync_min_age_hours', 12)
        time_budget = int_param('vkd_fios_api.daily_sync_time_budget', 600)

        now = fields.Datetime.now()
        cutoff = now - timedelta(hours=min_age_hours)
        domain = [
            ('fios_provision_state', '=', 'active'),
            ('fios_account_item_id', '!=', False),
            '|', ('fios_daily_sync_at', '=', False), ('fios_daily_sync_at', '<', cutoff),
        ]
        partners = self.sudo().search(domain, order='fios_daily_sync_at asc nulls first, id')
        if not partners:
            return

        win_start, win_end = self._fios_daily_sync_window(now)
        in_window = win_start <= now < win_end
        if in_window:
            slots_left = max(1, math.ceil((win_end - now).total_seconds() / (step_min * 60)))
            batch = partners[:math.ceil(len(partners) / slots_left)]
        else:
            batch = partners

        started = time.monotonic()
        done = failed = 0
        for partner in batch:
            if time.monotonic() - started > time_budget:
                break
            error = partner._fios_daily_sync_one()
            if error:
                failed += 1
                _logger.warning("FIOS daily sync: partner %s - %s", partner.id, error)
            else:
                done += 1
            # Each account is independent: keep what was done even if the
            # worker is killed later in the run.
            self.env.cr.commit()  # pylint: disable=invalid-commit

        remaining = len(partners) - done - failed
        _logger.info("FIOS daily sync: %s synced, %s failed, %s left", done, failed, remaining)
        if not remaining or not (done or failed):
            return
        cron = self.env.ref('vkd_fios_api.ir_cron_fios_daily_sync', raise_if_not_found=False)
        if not cron:
            return
        next_at = now + timedelta(minutes=step_min)
        if in_window and next_at < win_end:
            cron._trigger(at=next_at)
        else:
            # Past the window (or the time budget ran out on the last slot):
            # finish the rest straight away rather than leave it for tomorrow.
            cron._trigger()

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