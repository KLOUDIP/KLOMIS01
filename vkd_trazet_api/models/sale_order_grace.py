# -*- coding: utf-8 -*-
"""Trazet grace period: one per billing cycle, from either side, never both.

`grace_period_days` on its own records *what* grace a subscription carries but
not that it has been spent, so nothing stopped a customer being given a second
one - by the billing team after a self-service grant, or the other way round.
The fields below are that missing record: whichever side grants it stamps the
same lock, and both sides read the same lock before offering another.

The lock is tied to the billing cycle it was spent on (the subscription's
`next_invoice_date` at the moment of the grant), so it lifts by itself when the
subscription rolls on to its next invoice instead of needing to be cleared.
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DEFAULT_GRACE_DAYS = 7
GRACE_DAYS_PARAM = 'vkd_trazet_api.grace_period_days'
PORTAL_ENABLED_PARAM = 'vkd_trazet_api.grace_portal_enabled'

ACTIVE_SUBSCRIPTION_STATES = ('3_progress', '4_paused')


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    trazet_grace_granted_on = fields.Datetime(
        string='Grace Granted On', copy=False, readonly=True)
    trazet_grace_granted_by = fields.Many2one(
        'res.users', string='Grace Granted By', copy=False, readonly=True)
    trazet_grace_source = fields.Selection([
        ('backend', 'Billing Team'),
        ('portal', 'Customer Portal'),
    ], string='Grace Granted From', copy=False, readonly=True)
    trazet_grace_days_granted = fields.Integer(
        string='Grace Days Granted', copy=False, readonly=True)
    trazet_grace_expiry = fields.Date(
        string='Grace Ends On', copy=False, readonly=True,
        help='Invoice date the grace was granted against, plus the granted days.')
    trazet_grace_cycle_ref = fields.Date(
        string='Grace Used For Cycle', copy=False, readonly=True,
        help='The next invoice date this subscription had when the grace period '
             'was granted. The grace becomes available again once the '
             'subscription rolls on to a different invoice date.')

    trazet_grace_available = fields.Boolean(
        string='Grace Period Available', compute='_compute_trazet_grace_available',
        help='True when this customer can still be granted a grace period for '
             'the current billing cycle, from the backend or from the portal.')

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @api.model
    def _trazet_grace_days(self):
        """Length of the grace period, in days.

        Kept as a parameter rather than a constant so the offer can be changed
        without a code release; it still has to be one of the values
        `grace_period_days` accepts, otherwise the default stands.
        """
        raw = self.env['ir.config_parameter'].sudo().get_param(
            GRACE_DAYS_PARAM, str(DEFAULT_GRACE_DAYS))
        allowed = {value for value, _label in self._fields['grace_period_days'].selection}
        return int(raw) if str(raw) in allowed else DEFAULT_GRACE_DAYS

    @api.model
    def _trazet_grace_portal_enabled(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            PORTAL_ENABLED_PARAM, '1') in ('1', 'True', 'true')

    # ------------------------------------------------------------------
    # Eligibility
    # ------------------------------------------------------------------

    def _trazet_grace_eligible(self):
        """Whether a grace period could apply to this subscription at all.

        Free-plan and FIOS subscriptions are excluded for the same reason they
        are excluded from `_get_partner_closest_effective_date`: the first has
        no Trazet user to deactivate, the second syncs to FIOS instead.
        """
        self.ensure_one()
        return bool(
            self.is_subscription
            and self.state == 'sale'
            and self.subscription_state in ACTIVE_SUBSCRIPTION_STATES
            and self.next_invoice_date
            and self.partner_id.is_trazet_user
            and not self._is_fios_subscription()
            and not self._is_free_plan_subscription()
        )

    def _trazet_grace_locked(self):
        """True when this subscription's grace has been spent on its current cycle."""
        self.ensure_one()
        if not self.trazet_grace_granted_on:
            return False
        if not self.trazet_grace_cycle_ref or not self.next_invoice_date:
            # Nothing to roll over on; stay closed rather than re-opening on
            # every read. An administrator can clear it with the reset action.
            return True
        return self.trazet_grace_cycle_ref == self.next_invoice_date

    @api.model
    def _trazet_grace_subscriptions(self, partner):
        """The partner's subscriptions a grace period could be granted on."""
        if not partner:
            return self.browse()
        candidates = self.sudo().search([
            ('partner_id', '=', partner.id),
            ('is_subscription', '=', True),
            ('state', '=', 'sale'),
            ('subscription_state', 'in', list(ACTIVE_SUBSCRIPTION_STATES)),
            ('next_invoice_date', '!=', False),
        ])
        return candidates.filtered(lambda order: order._trazet_grace_eligible())

    @api.model
    def _trazet_grace_target(self, partner):
        """The subscription a new grace period would be granted on.

        Trazet is told a single deactivation date per user - the earliest one
        across the customer's subscriptions - so the grace has to land on the
        subscription that produces it, otherwise it would extend a date that is
        not the one cutting access off.
        """
        subscriptions = self._trazet_grace_subscriptions(partner)
        return self._trazet_grace_earliest(subscriptions)

    @api.model
    def _trazet_grace_earliest(self, subscriptions):
        if not subscriptions:
            return self.browse()
        return min(subscriptions, key=lambda order: order.next_invoice_date)

    @api.model
    def _trazet_grace_state(self, partner):
        """Everything the portal and the backend need to agree on one answer.

        Deliberately partner-wide: the grace is an allowance the *customer*
        gets, so a grace granted by the billing team on one subscription has to
        close the portal button on all of them, and the other way round.
        """
        subscriptions = self._trazet_grace_subscriptions(partner)
        locked = subscriptions.filtered(lambda order: order._trazet_grace_locked())
        # The most recent grant is the one to report on.
        current = max(
            locked, key=lambda order: order.trazet_grace_granted_on
        ) if locked else self.browse()
        target = self._trazet_grace_earliest(subscriptions)
        return {
            'days': self._trazet_grace_days(),
            'target': target,
            'eligible': bool(target),
            'locked': bool(current),
            'available': bool(target) and not current and self._trazet_grace_portal_enabled(),
            'granted_on': current.trazet_grace_granted_on or False,
            'granted_source': current.trazet_grace_source or False,
            'granted_days': current.trazet_grace_days_granted or 0,
            'expiry': current.trazet_grace_expiry or False,
            'subscription': current,
        }

    @api.depends('trazet_grace_granted_on', 'trazet_grace_cycle_ref',
                 'next_invoice_date', 'subscription_state', 'state')
    def _compute_trazet_grace_available(self):
        for order in self:
            order.trazet_grace_available = bool(
                order._trazet_grace_eligible()
                and not self._trazet_grace_state(order.partner_id)['locked']
            )

    # ------------------------------------------------------------------
    # Granting
    # ------------------------------------------------------------------

    @api.model
    def trazet_grant_partner_grace(self, partner, source='portal'):
        """Grant this customer their one grace period for the current cycle.

        Raises rather than returning a flag: both callers (the portal POST and
        the backend button) need the write rolled back when Trazet refuses the
        new deactivation date, so that a lock is never recorded for a grace the
        customer did not actually get.
        """
        state = self._trazet_grace_state(partner)
        if state['locked']:
            granted_on = state['granted_on']
            raise UserError(_(
                "A %(days)s-day grace period has already been used for this "
                "billing cycle%(when)s. It becomes available again on the next "
                "invoice date."
            ) % {
                'days': state['granted_days'] or state['days'],
                'when': (_(" (granted on %s)") % granted_on.date()) if granted_on else '',
            })
        order = state['target']
        if not order:
            raise UserError(_(
                "There is no active Trazet subscription on this account that a "
                "grace period can be applied to."))

        days = state['days']
        order = order.sudo()
        order.write({
            'grace_period_days': str(days),
            'trazet_grace_granted_on': fields.Datetime.now(),
            'trazet_grace_granted_by': self.env.user.id,
            'trazet_grace_source': source,
            'trazet_grace_days_granted': days,
            'trazet_grace_cycle_ref': order.next_invoice_date,
            'trazet_grace_expiry': order.next_invoice_date + timedelta(days=days),
        })

        success, message = order.update_partner_trazet_effective_date(partner)
        if not success:
            raise UserError(_(
                "The grace period could not be sent to Trazet (%s). "
                "Nothing has been changed - please try again.") % message)

        order.message_post(body=_(
            "%(days)s-day grace period granted from the %(source)s by %(user)s. "
            "Access now runs to %(expiry)s (invoice date %(invoice)s + %(days)s days)."
        ) % {
            'days': days,
            'source': _('customer portal') if source == 'portal' else _('billing team'),
            'user': self.env.user.name,
            'expiry': order.trazet_grace_expiry,
            'invoice': order.trazet_grace_cycle_ref,
        })
        _logger.info(
            "Trazet: %s-day grace period granted from %s for partner %s on %s",
            days, source, partner.id, order.name)
        return days

    def action_trazet_grant_grace(self):
        """Backend button: grant the grace period on the customer's behalf.

        Hiding the button in the view does not stop the RPC behind it, so the
        once-per-cycle rule is enforced in `trazet_grant_partner_grace` for
        both entry points rather than in the view.
        """
        self.ensure_one()
        days = self.trazet_grant_partner_grace(self.partner_id, source='backend')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Trazet Grace Period'),
                'message': _('%s-day grace period granted and sent to Trazet.') % days,
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def action_trazet_reset_grace(self):
        """Administrator escape hatch: clear the once-per-cycle lock.

        Needed to correct a grace granted in error, and for subscriptions with
        no invoice date to roll over on.
        """
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_("Only a system administrator can reset a grace period."))
        self.sudo().with_context(trazet_grace_bypass=True).write({
            'trazet_grace_granted_on': False,
            'trazet_grace_granted_by': False,
            'trazet_grace_source': False,
            'trazet_grace_days_granted': 0,
            'trazet_grace_expiry': False,
            'trazet_grace_cycle_ref': False,
        })
        self.message_post(body=_("Trazet grace period lock reset by %s.") % self.env.user.name)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Trazet Grace Period'),
                'message': _('Grace period reset - it can be granted again this cycle.'),
                'type': 'warning',
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    # ------------------------------------------------------------------
    # Enforcement
    # ------------------------------------------------------------------

    def write(self, vals):
        """Refuse to re-open a spent grace period by editing the field directly.

        Without this the backend selection would still be free to change after a
        portal grant, which is precisely the second grace period this feature
        exists to prevent. Only the field itself is guarded; everything else on
        the subscription writes normally.
        """
        if 'grace_period_days' in vals and not self.env.context.get('trazet_grace_bypass'):
            new_value = vals['grace_period_days'] or False
            for order in self:
                if (order.grace_period_days or False) == new_value:
                    continue
                if order._trazet_grace_locked():
                    raise UserError(_(
                        "The grace period for %(order)s has already been used for "
                        "this billing cycle (granted from the %(source)s on "
                        "%(date)s). Reset it first if it was recorded in error."
                    ) % {
                        'order': order.name,
                        'source': _('customer portal')
                                  if order.trazet_grace_source == 'portal'
                                  else _('billing team'),
                        'date': order.trazet_grace_granted_on,
                    })
        return super().write(vals)

    def action_send_effective_date_to_trazet(self):
        """Stamp the lock when the billing team sends a grace period through.

        The existing backend flow is "pick a grace period, then send it", so
        this - not the field write - is the moment the customer actually
        receives one, and therefore the moment the portal has to stop offering
        another.
        """
        result = super().action_send_effective_date_to_trazet()
        for order in self:
            # `_trazet_grace_locked` rather than "has a grant on record": the
            # stamp has to be refreshed once the subscription rolls into a new
            # cycle, otherwise the first grant would lock the field for good.
            if not order.grace_period_days or order._trazet_grace_locked():
                continue
            if not order._trazet_grace_eligible():
                continue
            days = int(order.grace_period_days)
            order.sudo().with_context(trazet_grace_bypass=True).write({
                'trazet_grace_granted_on': fields.Datetime.now(),
                'trazet_grace_granted_by': self.env.user.id,
                'trazet_grace_source': 'backend',
                'trazet_grace_days_granted': days,
                'trazet_grace_cycle_ref': order.next_invoice_date,
                'trazet_grace_expiry': order.next_invoice_date + timedelta(days=days),
            })
        return result
