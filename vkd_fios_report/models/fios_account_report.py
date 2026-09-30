# -*- coding: utf-8 -*-
import logging
import time
from datetime import timedelta

import pytz

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# How many contacts the list's "Refresh from FIOS" button handles in one click.
# Every contact is several FIOS API calls, so a large selection belongs to the
# scheduled action instead.
MANUAL_REFRESH_LIMIT = 50


class VkdFiosAccountReport(models.Model):
    """One line per FIOS contact whose status has been read from FIOS.

    A SQL view over res.partner and fios.device, so every column can be
    filtered, grouped, sorted, pivoted and exported with no stored duplicates
    on res.partner to keep in step.

    "Synced" means the live status has been read at least once
    (fios_status_synced is set). Before that, fios_account_enabled is still at
    its default False, which makes vkd_fios_api's computed status say
    "Blocked" for an account nobody has looked at. Those contacts are left out.
    """
    _name = 'vkd.fios.account.report'
    _description = 'FIOS Account Report'
    _auto = False
    _rec_name = 'partner_id'
    _order = 'account_status, days_left, partner_id'

    partner_id = fields.Many2one('res.partner', string='Contact', readonly=True)
    tier_id = fields.Many2one('fios.service.tier', string='Service Tier', readonly=True)
    current_plan = fields.Char(string='FIOS Plan', readonly=True)

    account_status = fields.Selection([
        ('active', 'Active'),
        ('blocked', 'Blocked'),
    ], string='Status', readonly=True)

    # Units
    active_unit_count = fields.Integer(string='Active Units', readonly=True)
    inactive_unit_count = fields.Integer(string='Inactive Units', readonly=True)
    unit_count = fields.Integer(string='Total Units', readonly=True)

    # Days left. FIOS counts the block-by-days counter down once a day and
    # blocks the account when it reaches -1. Odoo only holds the value read at
    # the last sync, so today's figure is derived from it.
    days_counter = fields.Integer(
        string='Days Left (at Sync)', readonly=True, aggregator='min',
        help='FIOS days counter as read at the last sync.')
    days_left = fields.Integer(
        string='Days Left', readonly=True, aggregator='min',
        help='Days left before FIOS blocks the account, counted from today: the '
             'counter at the last sync minus the days since then. Empty for '
             'blocked accounts.')
    block_date = fields.Date(
        string='Blocks On', readonly=True,
        help='Estimated date FIOS blocks the account (the day the counter reaches -1). '
             'Empty for blocked accounts.')
    next_due_date = fields.Date(string='Days Left Run To', readonly=True)
    days_left_source = fields.Char(string='Days Left Based On', readonly=True)
    counter_synced = fields.Datetime(
        string='Counter Synced At', readonly=True,
        help='When the days counter was last read from or pushed to FIOS.')
    status_synced = fields.Datetime(string='Status Read At', readonly=True)

    # 7-day grace period
    grace_status = fields.Selection([
        ('in_use', 'In Use'),
        ('not_in_use', 'Not In Use'),
    ], string='Grace Period', readonly=True,
        help='In Use: a grace period was granted and has not ended yet.')
    grace_expiry = fields.Date(string='Grace Ends On', readonly=True)
    grace_granted_on = fields.Datetime(string='Grace Granted On', readonly=True)
    grace_source = fields.Selection([
        ('backend', 'Billing Team'),
        ('portal', 'Customer Portal'),
    ], string='Grace Granted From', readonly=True)
    grace_granted_by = fields.Many2one('res.users', string='Grace Granted By', readonly=True)

    # ------------------------------------------------------------------
    # SQL view
    # ------------------------------------------------------------------

    @api.model
    def _vkd_report_timezone(self):
        """Timezone that decides what "today" is for days left and grace.

        Order: the vkd_fios_report.timezone system parameter, then the admin
        user's timezone, then UTC. Baked into the view when the module is
        installed or upgraded - upgrade it after changing either.
        """
        candidates = [
            self.env['ir.config_parameter'].sudo().get_param('vkd_fios_report.timezone'),
        ]
        admin = self.env.ref('base.user_admin', raise_if_not_found=False)
        if admin:
            candidates.append(admin.sudo().tz)
        for tz in candidates:
            if tz and tz in pytz.all_timezones_set:
                return tz
        return 'UTC'

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        # Odoo stores datetimes as UTC "timestamp without time zone":
        # (x AT TIME ZONE 'UTC') makes it tz-aware, AT TIME ZONE <tz> gives
        # local wall time. Without this a sync just after local midnight would
        # land on the previous day and throw days left off by one.
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW vkd_fios_account_report AS (
                WITH ctx AS (
                    SELECT (now() AT TIME ZONE %(tz)s)::date AS today
                ),
                units AS (
                    SELECT partner_id,
                           count(*) FILTER (WHERE device_active) AS active_units,
                           count(*) FILTER (WHERE device_active IS NOT TRUE) AS inactive_units,
                           count(*) AS all_units
                      FROM fios_device
                     GROUP BY partner_id
                ),
                base AS (
                    SELECT p.id,
                           p.fios_tier_id,
                           p.fios_current_plan,
                           p.fios_account_status,
                           COALESCE(p.fios_days_counter, 0) AS days_counter,
                           p.fios_next_due_date,
                           p.fios_days_left_source,
                           p.fios_status_synced,
                           GREATEST(p.fios_status_synced, p.fios_days_left_synced) AS counter_synced,
                           p.fios_grace_expiry,
                           p.fios_grace_granted_on,
                           p.fios_grace_source,
                           p.fios_grace_granted_by
                      FROM res_partner p
                     WHERE p.active
                       AND p.fios_provision_state = 'active'
                       AND p.fios_account_item_id IS NOT NULL
                       AND p.fios_account_item_id != ''
                       AND p.fios_status_synced IS NOT NULL
                       AND p.fios_account_status IN ('active', 'blocked')
                )
                SELECT b.id,
                       b.id AS partner_id,
                       b.fios_tier_id AS tier_id,
                       b.fios_current_plan AS current_plan,
                       b.fios_account_status AS account_status,
                       COALESCE(u.active_units, 0) AS active_unit_count,
                       COALESCE(u.inactive_units, 0) AS inactive_unit_count,
                       COALESCE(u.all_units, 0) AS unit_count,
                       b.days_counter,
                       CASE WHEN b.fios_account_status = 'active' THEN
                           b.days_counter - (ctx.today - ((b.counter_synced AT TIME ZONE 'UTC')
                                                          AT TIME ZONE %(tz)s)::date)
                       END AS days_left,
                       CASE WHEN b.fios_account_status = 'active' THEN
                           ((b.counter_synced AT TIME ZONE 'UTC') AT TIME ZONE %(tz)s)::date
                               + b.days_counter + 1
                       END AS block_date,
                       b.fios_next_due_date AS next_due_date,
                       b.fios_days_left_source AS days_left_source,
                       b.counter_synced,
                       b.fios_status_synced AS status_synced,
                       CASE WHEN b.fios_grace_granted_on IS NOT NULL
                                 AND b.fios_grace_expiry >= ctx.today
                            THEN 'in_use' ELSE 'not_in_use'
                       END AS grace_status,
                       b.fios_grace_expiry AS grace_expiry,
                       b.fios_grace_granted_on AS grace_granted_on,
                       b.fios_grace_source AS grace_source,
                       b.fios_grace_granted_by AS grace_granted_by
                  FROM base b
                 CROSS JOIN ctx
                  LEFT JOIN units u ON u.partner_id = b.id
            )
        """, {'tz': self._vkd_report_timezone()})

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_open_partner(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_refresh_from_fios(self):
        """Re-read status and devices from FIOS for the selected lines."""
        if not self.env.user.has_group('vkd_fios_api.group_fios_user'):
            raise UserError(_("Only the FIOS billing team can refresh FIOS accounts."))
        if len(self) > MANUAL_REFRESH_LIMIT:
            raise UserError(_(
                "Select at most %(limit)s lines to refresh at once (%(count)s selected). "
                "All accounts are refreshed every night by the scheduled action "
                "'FIOS Report: Refresh Account Status and Devices'.",
                limit=MANUAL_REFRESH_LIMIT, count=len(self)))
        partners = self.mapped('partner_id')
        failed = []
        for partner in partners:
            error = self._vkd_refresh_partner(partner)
            if error:
                failed.append("%s: %s" % (partner.display_name, error))
        done = len(partners) - len(failed)
        if failed:
            message = _("%(done)s refreshed, %(failed)s failed:\n%(errors)s",
                        done=done, failed=len(failed), errors="\n".join(failed))
        else:
            message = _("%s account(s) refreshed from FIOS.", done)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('FIOS Report'),
                'message': message,
                'type': 'warning' if failed else 'success',
                'sticky': bool(failed),
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    @api.model
    def _vkd_refresh_partner(self, partner):
        """Read status + devices for one contact. Returns an error text or None.

        Read-only towards FIOS: nothing is pushed, so running it any number of
        times cannot change a customer's access. A savepoint keeps one failing
        account from rolling back the others.
        """
        partner = partner.sudo()
        try:
            with self.env.cr.savepoint():
                self.env['fios.provisioning'].refresh_account_status(partner)
                partner.action_fios_refresh_devices()
        except Exception as e:  # noqa: BLE001 - reported per account, run continues
            _logger.warning("FIOS report: refresh failed for partner %s: %s", partner.id, e)
            return str(e) or e.__class__.__name__
        return None

    @api.model
    def _cron_refresh_fios_accounts(self):
        """Nightly: re-read status and devices of every active FIOS account.

        Oldest-synced first. Works within a time budget and re-triggers itself
        for the rest, so a long list never runs into the cron time limit. Only
        accounts not synced within the last `vkd_fios_report.refresh_min_age_hours`
        hours are picked, which is also what stops the continuation from
        re-reading accounts the same run already did.
        """
        icp = self.env['ir.config_parameter'].sudo()
        min_age_hours = int(icp.get_param('vkd_fios_report.refresh_min_age_hours', 20))
        time_budget = int(icp.get_param('vkd_fios_report.refresh_time_budget', 600))

        cutoff = fields.Datetime.now() - timedelta(hours=min_age_hours)
        partners = self.env['res.partner'].sudo().search([
            ('fios_provision_state', '=', 'active'),
            ('fios_account_item_id', '!=', False),
            '|', ('fios_status_synced', '=', False),
                 ('fios_status_synced', '<', cutoff),
        ], order='fios_status_synced asc nulls first, id')

        started = time.monotonic()
        done = failed = 0
        for partner in partners:
            if time.monotonic() - started > time_budget:
                break
            if self._vkd_refresh_partner(partner):
                failed += 1
            else:
                done += 1
            # Each account is independent: keep what was read even if the
            # worker is killed later in the run.
            self.env.cr.commit()  # pylint: disable=invalid-commit

        remaining = len(partners) - done - failed
        _logger.info("FIOS report: nightly refresh - %s refreshed, %s failed, %s left for "
                     "the next run", done, failed, remaining)
        # Continue only if this run made progress; otherwise a set of accounts
        # that always fail could keep the job re-triggering itself.
        if remaining and done:
            cron = self.env.ref('vkd_fios_report.ir_cron_fios_report_refresh',
                                raise_if_not_found=False)
            if cron:
                cron._trigger()
