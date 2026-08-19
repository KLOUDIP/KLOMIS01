# -*- coding: utf-8 -*-
import logging

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

    def _sync_fios_billing_date(self, partner, description=None):
        if partner.fios_provision_state != 'active' or not partner.fios_account_item_id:
            return True, None
        next_date = self._fios_earliest_next_invoice_date(partner)
        if not next_date:
            return True, None

        target = (next_date - fields.Date.today()).days
        if target < 0:
            target = 0

        client = self.env['fios.api.client']
        log = self.env['fios.api.log']
        item_id = int(partner.fios_account_item_id)
        try:
            data = client.call('account/get_account_data', {'itemId': item_id, 'type': 2},
                               tier=partner.fios_tier_id)
        except Exception as e:
            _logger.warning("FIOS: could not read daysCounter for partner %s: %s", partner.id, e)
            return False, str(e)

        current = data.get('daysCounter') or 0
        delta = target - current
        if delta == 0:
            return True, None

        params = {
            'itemId': item_id,
            'balanceUpdate': 0,
            'daysUpdate': delta,
            'description': description or _("Subscription billing update"),
        }
        try:
            result = client.call('account/do_payment', params, tier=partner.fios_tier_id)
        except Exception as e:
            log.log_failure('account/do_payment', params, partner=partner, error_msg=str(e), retryable=True)
            return False, str(e)
        log.log_success('account/do_payment', params, partner=partner, response_data=result,
                        message=_("FIOS billing date synced (target %s days, delta %s)") % (target, delta))
        _logger.info("FIOS: billing date synced for partner %s (target=%s, delta=%s)",
                     partner.id, target, delta)
        return True, None

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
