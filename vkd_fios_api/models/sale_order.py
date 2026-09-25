# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

# Subscription states considered "live" when summing service limits.
ACTIVE_SUB_STATES = ['3_progress', '4_paused']


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_fios_free_subscription = fields.Boolean(
        string='Is FIOS Free Subscription?',
        copy=False,
        default=False,
        help='Marks the free subscription auto-created for a new FIOS customer.',
    )

    def _calculate_fios_service_limits(self, partner=None):
        if not partner:
            self.ensure_one()
            partner = self.partner_id

        active_subscriptions = self.env['sale.order'].search([
            ('partner_id', '=', partner.id),
            ('is_subscription', '=', True),
            ('subscription_state', 'in', ACTIVE_SUB_STATES),
            ('state', '=', 'sale'),
        ])
        # Include a subscription currently being confirmed.
        if (self.is_subscription and self.state in ('draft', 'sent')
                and self.partner_id.id == partner.id):
            active_subscriptions |= self

        limits = {}
        for subscription in active_subscriptions:
            lines = subscription.order_line.filtered(
                lambda l: l.recurring_invoice and l.product_id.product_tmpl_id.fios_service)
            for line in lines:
                service = line.product_id.product_tmpl_id.fios_service
                limits[service] = limits.get(service, 0) + int(line.product_uom_qty)
        return limits

    def _send_fios_limits_update(self, partner, service_limits):
        if not service_limits:
            return True, None
        if partner.fios_provision_state != 'active' or not partner.fios_account_item_id:
            _logger.info("FIOS: partner %s has no active account; skipping limits update", partner.id)
            return True, None

        from .fios_provisioning import fios_service_type, fios_cost_table
        item_id = int(partner.fios_account_item_id)
        subs = [{
            'svc': 'account/update_billing_service',
            'params': {
                'itemId': item_id,
                'name': service,
                'type': fios_service_type(service),
                'intervalType': 0,
                'costTable': fios_cost_table(service, qty),
            },
        } for service, qty in service_limits.items()]
        batch = {'params': subs, 'flags': 0}

        client = self.env['fios.api.client']
        log = self.env['fios.api.log']
        provisioning = self.env['fios.provisioning']
        try:
            result = client.call('core/batch', batch, tier=partner.fios_tier_id)
        except Exception as e:
            log.log_failure('core/batch', batch, partner=partner, error_msg=str(e), retryable=True)
            _logger.warning("FIOS: limits update failed for partner %s: %s", partner.id, e)
            return False, str(e)

        batch_error = provisioning._batch_error(result)
        if batch_error:
            log.log_failure('core/batch', batch, partner=partner, error_msg=batch_error, retryable=True)
            return False, batch_error

        log.log_success('core/batch', batch, partner=partner, response_data=result,
                        message=_("FIOS service limits updated: %s") % service_limits)
        _logger.info("FIOS: limits updated for partner %s -> %s", partner.id, service_limits)
        return True, None

    def _sync_fios_limits(self, partner):
        """Recompute and push the current service limits for a partner."""
        limits = self._calculate_fios_service_limits(partner)
        return self._send_fios_limits_update(partner, limits)

    def _calculate_projected_fios_limits_after_decrease(self, decrease_lines):
        self.ensure_one()
        partner = self.partner_id
        new_qty_by_line = {int(k): float(v) for k, v in (decrease_lines or {}).items()}
        limits = {}
        for sub in self._partner_active_subscriptions(partner):
            lines = sub.order_line.filtered(
                lambda l: l.recurring_invoice and l.product_id.product_tmpl_id.fios_service)
            for line in lines:
                service = line.product_id.product_tmpl_id.fios_service
                qty = new_qty_by_line.get(line.id, line.product_uom_qty)
                limits[service] = limits.get(service, 0) + int(qty)
        return limits

    def _fios_check_usage_allows(self, partner, projected_limits):
        if not projected_limits:
            return True, None
        if partner.fios_provision_state != 'active' or not partner.fios_account_item_id:
            return True, None
        provisioning = self.env['fios.provisioning']
        try:
            data = provisioning.get_account_data(partner)
        except Exception as e:
            return False, _("Could not verify FIOS usage: %s") % e
        services = ((data.get('settings') or {}).get('combined') or {}).get('services') or {}
        labels = dict(provisioning.TRACKED_SERVICES)
        for service, new_limit in projected_limits.items():
            usage = (services.get(service) or {}).get('usage', 0) or 0
            if new_limit < usage:
                return False, _(
                    "Cannot reduce %(label)s to %(limit)s - you are currently using %(usage)s. "
                    "Please log in to FIOS, delete the unwanted items to bring usage down to "
                    "%(limit)s or fewer, then come back and reduce."
                ) % {'label': labels.get(service, service), 'limit': new_limit, 'usage': usage}
        return True, None

    def _partner_active_subscriptions(self, partner, exclude=None):
        domain = [
            ('partner_id', '=', partner.id),
            ('is_subscription', '=', True),
            ('subscription_state', 'in', ACTIVE_SUB_STATES),
            ('state', '=', 'sale'),
        ]
        if exclude:
            domain.append(('id', '!=', exclude.id))
        return self.env['sale.order'].search(domain)

    def _fios_earliest_next_invoice_date(self, partner, exclude=None):
        dates = [
            s.next_invoice_date
            for s in self._partner_active_subscriptions(partner, exclude=exclude)
            if s.next_invoice_date
        ]
        return min(dates) if dates else False

    # ------------------------------------------------------------------
    # FIOS "days left" (block-by-days counter)
    # ------------------------------------------------------------------
    # The counter FIOS shows as "Days Left" is driven by the customer's
    # invoices, and only falls back to the subscription when nothing is owed:
    #
    #   1. Open invoices exist (hardware, subscription, anything - not paid or
    #      partly paid): days left = days until the EARLIEST invoice due date.
    #      Paying that invoice moves the counter on to the next one due.
    #   2. Everything is paid: days left = days until the paid subscription
    #      period runs out (see _fios_paid_up_until). An early payer, or an
    #      annual subscription paid up front, keeps access for the period
    #      already paid for.
    #   3. Nothing to go on (no open invoice, no subscription period ahead of
    #      today - e.g. a new subscription whose first invoice is not raised
    #      yet): the counter is left as it is.
    #
    # The counter is re-synced whenever an invoice is posted, paid, reset to
    # draft / cancelled, or has a payment removed (see account_move.py).

    def _fios_icp_flag(self, key, default='0'):
        value = self.env['ir.config_parameter'].sudo().get_param(key, default)
        return str(value).strip().lower() in ('1', 'true', 'yes')

    def _fios_invoice_scope_is_fios_only(self):
        """'all' (default): every open customer invoice of the customer counts.
        'fios': only invoices carrying at least one FIOS product."""
        scope = self.env['ir.config_parameter'].sudo().get_param(
            'vkd_fios_api.days_left_invoice_scope', 'all')
        return str(scope).strip().lower() == 'fios'

    @api.model
    def _fios_invoice_domain_fios_only(self):
        return ['|',
                ('invoice_line_ids.product_id.product_tmpl_id.fios_service', '!=', False),
                ('invoice_line_ids.product_id.product_tmpl_id.fios_tier_id', '!=', False)]

    def _fios_open_invoices(self, partner):
        """Customer invoices of the partner's commercial entity that still have
        something to pay. Invoice-type child addresses ("..., Contact - I") are
        included through the commercial partner."""
        commercial = partner.commercial_partner_id or partner
        states = ['posted']
        # Drafts are ignored by default: a draft without an invoice date gets a
        # due date computed from *today*, so it would slide every day.
        if self._fios_icp_flag('vkd_fios_api.days_left_include_draft'):
            states.append('draft')
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('commercial_partner_id', '=', commercial.id),
            ('state', 'in', states),
            ('invoice_date_due', '!=', False),
            ('payment_state', 'in', ('not_paid', 'partial')),
        ]
        if self._fios_invoice_scope_is_fios_only():
            domain += self._fios_invoice_domain_fios_only()
        return self.env['account.move'].sudo().search(domain)

    @api.model
    def _fios_term_due_date(self, payment_term, date_ref):
        """Due date an invoice dated `date_ref` gets under `payment_term`
        (the last instalment, same as account.move.invoice_date_due)."""
        if not payment_term or not payment_term.line_ids:
            return date_ref
        try:
            return max(line._get_due_date(date_ref) for line in payment_term.line_ids)
        except Exception as e:  # never let a term misconfiguration break billing
            _logger.warning("FIOS: could not apply payment term %s to %s: %s",
                            payment_term.id, date_ref, e)
            return date_ref

    def _fios_days_left_subscriptions(self, partner):
        """Live subscriptions of the customer (whole commercial entity, like the
        invoices), limited to FIOS subscriptions when the scope is 'fios'."""
        commercial = partner.commercial_partner_id or partner
        subs = self.env['sale.order'].sudo().search([
            ('partner_id', 'child_of', commercial.id),
            ('is_subscription', '=', True),
            ('subscription_state', 'in', ACTIVE_SUB_STATES),
            ('state', '=', 'sale'),
        ])
        if self._fios_invoice_scope_is_fios_only():
            subs = subs.filtered(lambda s: any(
                line.product_id.product_tmpl_id.fios_service
                or line.product_id.product_tmpl_id.fios_tier_id
                for line in s.order_line))
        return subs

    def _fios_paid_up_until(self, subscription):
        """Date access runs to when the subscription has nothing left to pay.

        `vkd_fios_api.days_left_paid_up_basis`:
          next_invoice_date (default) - up to and including the day the next
              period's invoice is raised. That invoice is synced as soon as it
              is posted, so the customer is never cut off in the gap between
              one period ending and its invoice being generated.
          period_end - up to the last day of the paid period
              (next invoice date - 1 day).
        A subscription end date earlier than that wins in both cases.
        """
        next_date = subscription.next_invoice_date
        if not next_date:
            return False
        basis = self.env['ir.config_parameter'].sudo().get_param(
            'vkd_fios_api.days_left_paid_up_basis', 'next_invoice_date')
        until = next_date
        if str(basis).strip().lower() == 'period_end':
            until = next_date - timedelta(days=1)
        end_date = getattr(subscription, 'end_date', False)
        if end_date and end_date < until:
            until = end_date
        return until

    def _fios_next_due_info(self, partner):
        """(date, source label, basis) that the days-left counter should run to.

        basis is 'invoice', 'subscription' or None (nothing to sync from).
        """
        invoices = self._fios_open_invoices(partner)
        if invoices:
            inv = min(invoices, key=lambda m: (m.invoice_date_due, m.id))
            label = inv.name if inv.name and inv.name != '/' else _("draft invoice %s") % inv.id
            return inv.invoice_date_due, label, 'invoice'

        # Nothing owed: fall back to the paid subscription period. A date that
        # is not after today means the period's invoice is due to be raised
        # (or the subscription has not been invoiced yet) - leave the counter
        # alone rather than cut access before that invoice exists.
        today = fields.Date.context_today(self)
        candidates = []
        for sub in self._fios_days_left_subscriptions(partner):
            until = self._fios_paid_up_until(sub)
            if until and until > today:
                candidates.append((until, sub.id, _("paid subscription period of %s") % sub.name))
        if not candidates:
            return False, None, None
        until, _sub_id, label = min(candidates)
        return until, label, 'subscription'

    def _fios_push_days_left(self, partner, description=None):
        """Set the FIOS days counter to the days left until the next due date.

        Returns a dict: ok, error, changed, days, due_date, source, basis.
        """
        res = {'ok': True, 'error': None, 'changed': False,
               'days': None, 'due_date': False, 'source': None, 'basis': None}
        partner = partner.sudo()
        if partner.fios_provision_state != 'active' or not partner.fios_account_item_id:
            return res
        due_date, source, basis = self._fios_next_due_info(partner)
        if not due_date:
            return res

        client = self.env['fios.api.client']
        log = self.env['fios.api.log']
        item_id = int(partner.fios_account_item_id)
        try:
            data = client.call('account/get_account_data', {'itemId': item_id, 'type': 2},
                               tier=partner.fios_tier_id)
        except Exception as e:
            _logger.warning("FIOS: could not read daysCounter for partner %s: %s", partner.id, e)
            res.update(ok=False, error=str(e))
            return res
        current = data.get('daysCounter') or 0

        today = fields.Date.context_today(self)
        target = (due_date - today).days
        if target < 0:
            # An invoice is overdue. An account that FIOS has already blocked
            # (counter below zero) stays blocked - paying some other invoice or
            # raising a new one must not reopen it. Otherwise 0 keeps today's
            # access and FIOS blocks on its next daily decrement.
            target = current if current < 0 else 0
        # Never cut into a grace period that is still running.
        if partner.fios_grace_expiry and partner.fios_grace_expiry >= today:
            target = max(target, (partner.fios_grace_expiry - today).days)
        res.update(days=target, due_date=due_date, source=source, basis=basis)

        sync_vals = {
            'fios_next_due_date': due_date,
            'fios_days_left_source': source,
            'fios_days_left_synced': fields.Datetime.now(),
        }
        delta = target - current
        if delta == 0:
            sync_vals['fios_days_counter'] = target
            partner.write(sync_vals)
            return res

        params = {
            'itemId': item_id,
            'balanceUpdate': 0,
            'daysUpdate': delta,
            'description': (description or _("Subscription billing update"))[:250],
        }
        try:
            result = client.call('account/do_payment', params, tier=partner.fios_tier_id)
        except Exception as e:
            # retryable=False on purpose: do_payment applies a *delta* and the
            # retry cron replays the stored params as-is, which would add the
            # delta twice if FIOS had in fact applied it. The next sync
            # recomputes the correct delta from the live counter instead.
            log.log_failure('account/do_payment', params, partner=partner,
                            error_msg=str(e), retryable=False)
            res.update(ok=False, error=str(e))
            return res
        log.log_success('account/do_payment', params, partner=partner, response_data=result,
                        message=_("FIOS days left set to %(target)s (was %(current)s, delta "
                                  "%(delta)s) - runs to %(due)s from %(source)s")
                        % {'target': target, 'current': current, 'delta': delta,
                           'due': due_date, 'source': source})
        sync_vals['fios_days_counter'] = target
        partner.write(sync_vals)
        _logger.info("FIOS: days left synced for partner %s (target=%s, delta=%s, date=%s, %s)",
                     partner.id, target, delta, due_date, source)
        res['changed'] = True
        return res

    def _sync_fios_billing_date(self, partner, description=None):
        res = self._fios_push_days_left(partner, description=description)
        return res['ok'], res['error']

    def _fios_set_enabled(self, partner, enabled):
        if partner.fios_provision_state != 'active' or not partner.fios_account_item_id:
            return True, None
        if partner.fios_account_enabled == enabled:
            return True, None  # already in the desired state
        client = self.env['fios.api.client']
        log = self.env['fios.api.log']
        params = {'itemId': int(partner.fios_account_item_id), 'enable': 1 if enabled else 0}
        try:
            result = client.call('account/enable_account', params, tier=partner.fios_tier_id)
        except Exception as e:
            log.log_failure('account/enable_account', params, partner=partner, error_msg=str(e), retryable=True)
            return False, str(e)
        partner.sudo().fios_account_enabled = enabled
        log.log_success('account/enable_account', params, partner=partner, response_data=result,
                        message=_("FIOS account %s") % ('enabled' if enabled else 'disabled'))
        _logger.info("FIOS: account %s for partner %s", 'enabled' if enabled else 'disabled', partner.id)
        return True, None

    def _fios_subscription_tier(self):
        self.ensure_one()
        for line in self.order_line.filtered(lambda l: l.recurring_invoice):
            tier = line.product_id.product_tmpl_id.fios_tier_id
            if tier:
                return tier
        return self.env['fios.service.tier']

    def action_confirm(self):
        result = super().action_confirm()

        new_subscriptions = self.filtered(
            lambda o: o.is_subscription
            and o.subscription_state == '3_progress'
            and not o.subscription_id
        )
        for subscription in new_subscriptions:
            tier = subscription._fios_subscription_tier()
            if tier and subscription.partner_id.is_fios_user:
                # Do NOT provision inline - the FIOS API sequence is slow and would
                # block checkout. Stamp the tier and mark pending; the cron
                # (cron_process_fios_provisioning) provisions + syncs in the
                # background.
                vals = {'fios_provision_pending': True}
                if subscription.partner_id.fios_tier_id != tier:
                    vals['fios_tier_id'] = tier.id
                subscription.partner_id.write(vals)
        return result

    def update_existing_subscriptions(self):
        result = super().update_existing_subscriptions()
        for order in self:
            if order.subscription_state == '7_upsell' and order.subscription_id:
                main = order.subscription_id
                if main.partner_id.fios_provision_state == 'active':
                    main._sync_fios_limits(main.partner_id)
                    main._sync_fios_billing_date(main.partner_id, description=main.name)
        return result

    def set_close(self, close_reason_id=None, renew=False):
        result = super().set_close(close_reason_id=close_reason_id, renew=renew)
        for order in self:
            if not (order.is_subscription and order.partner_id.fios_provision_state == 'active'):
                continue
            partner = order.partner_id
            if self._partner_active_subscriptions(partner, exclude=order):
                # Other subscriptions remain: recompute limits and billing date.
                order._sync_fios_limits(partner)
                order._sync_fios_billing_date(partner, description=order.name)
            else:
                # Nothing active left -> disable the FIOS account.
                order._fios_set_enabled(partner, False)
        return result
