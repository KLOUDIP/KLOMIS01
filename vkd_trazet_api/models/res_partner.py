from markupsafe import Markup, escape

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

TRAZET_ACTIVE_STATES = ('3_progress', '4_paused')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_trazet_user = fields.Boolean(string='Is Trazet User?', copy=False, default=False, help='Is the user allowed to use the API Operations?')

    # ------------------------------------------------------------------
    # TRAZET tab (contact form) - read-only view of what Odoo syncs to
    # Trazet for this customer. Nothing below is stored: every value is
    # derived from the same helpers the sync itself uses on sale.order, so
    # the tab can never disagree with what is actually sent.
    # ------------------------------------------------------------------

    # Trazet addresses a customer by the Odoo res.users id
    # (/api/v2/odoo/<user id>/limits, /deactivate), not by the partner id.
    trazet_user_id = fields.Integer(
        string='Trazet User ID', compute='_compute_trazet_account',
        help='Odoo user id this customer is known by in Trazet. Trazet API calls '
             'are addressed to /api/v2/odoo/<this id>/...')
    trazet_login = fields.Char(string='Portal Login', compute='_compute_trazet_account')
    trazet_is_integrator = fields.Boolean(
        string='Integrator', compute='_compute_trazet_account',
        help='Integrator users are synced with the separate integrator API token.')

    trazet_subscription_ids = fields.Many2many(
        'sale.order', string='Trazet Subscriptions',
        compute='_compute_trazet_subscriptions',
        help='Active (in progress / paused) confirmed subscriptions that sync to '
             'Trazet. FIOS subscriptions sync to FIOS and are left out.')
    trazet_limits_html = fields.Html(
        string='Limits Sent to Trazet', compute='_compute_trazet_subscriptions',
        sanitize=False,
        help='Product limits Odoo computes from all active subscriptions - the '
             'payload of the next limits sync.')

    trazet_effective_date = fields.Date(
        string='Access Valid Until', compute='_compute_trazet_effective_date',
        help='Deactivation date Odoo sends to Trazet: the earliest next invoice '
             'date (+ grace period) across active paid, non-FIOS subscriptions.')
    trazet_effective_subscription_id = fields.Many2one(
        'sale.order', string='Date Taken From', compute='_compute_trazet_effective_date')
    trazet_effective_note = fields.Char(string='Basis', compute='_compute_trazet_effective_date')

    trazet_grace_available = fields.Boolean(compute='_compute_trazet_grace')
    trazet_grace_days = fields.Integer(string='Grace Period Length', compute='_compute_trazet_grace')
    trazet_grace_granted_on = fields.Datetime(string='Grace Granted On', compute='_compute_trazet_grace')
    trazet_grace_source = fields.Char(string='Granted From', compute='_compute_trazet_grace')
    trazet_grace_days_granted = fields.Integer(string='Grace Days Granted', compute='_compute_trazet_grace')
    trazet_grace_expiry = fields.Date(string='Grace Ends On', compute='_compute_trazet_grace')
    trazet_grace_subscription_id = fields.Many2one(
        'sale.order', string='Grace On Subscription', compute='_compute_trazet_grace')

    trazet_api_log_ids = fields.One2many('api.retry.log', 'partner_id', string='Trazet API Logs')
    trazet_api_log_count = fields.Integer(compute='_compute_trazet_api_status')
    trazet_last_sync = fields.Datetime(
        string='Trazet Last Sync', compute='_compute_trazet_api_status',
        help='Time of the last successful Trazet API call for this customer.')
    trazet_last_error = fields.Text(
        string='Trazet Last Error', compute='_compute_trazet_api_status',
        help='Error of the latest pending / failed Trazet API call, when it is '
             'newer than the last successful one.')

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends('user_ids', 'user_ids.login', 'user_ids.is_integrator')
    def _compute_trazet_account(self):
        for partner in self:
            user = partner.sudo().user_ids[:1]
            partner.trazet_user_id = user.id or 0
            partner.trazet_login = user.login or False
            partner.trazet_is_integrator = bool(user.is_integrator)

    def _trazet_active_subscriptions(self):
        """Mirror of the domain used by _calculate_trazet_product_limits /
        _get_partner_closest_effective_date, minus FIOS subscriptions."""
        self.ensure_one()
        partner = self._origin
        if not partner:
            return self.env['sale.order']
        subscriptions = self.env['sale.order'].sudo().search([
            ('partner_id', '=', partner.id),
            ('is_subscription', '=', True),
            ('subscription_state', 'in', list(TRAZET_ACTIVE_STATES)),
            ('state', '=', 'sale'),
        ], order='next_invoice_date, id')
        return subscriptions.filtered(lambda order: not order._is_fios_subscription())

    def _compute_trazet_subscriptions(self):
        SaleOrder = self.env['sale.order'].sudo()
        key_labels = dict(
            self.env['product.template']._fields['trazet_product_key'].selection)
        for partner in self:
            origin = partner._origin  # empty on an unsaved contact
            if not partner.is_trazet_user or not origin:
                partner.trazet_subscription_ids = False
                partner.trazet_limits_html = False
                continue
            partner.trazet_subscription_ids = partner._trazet_active_subscriptions()
            try:
                limits = SaleOrder._calculate_trazet_product_limits(origin)
            except Exception as e:  # never break the contact form over a preview
                _logger.warning("Trazet: could not compute limits for partner %s: %s", partner.id, e)
                partner.trazet_limits_html = Markup('<p class="text-muted">%s</p>') % _(
                    "Could not compute the Trazet limits: %s", e)
                continue
            rows = Markup('').join(
                Markup('<tr><td>%s</td><td class="text-muted small">%s</td><td class="text-end fw-bold">%s</td></tr>') % (
                    key_labels.get(key, key), key, partner._trazet_format_limit(value))
                for key, value in limits.items()
            )
            partner.trazet_limits_html = Markup(
                '<table class="table table-sm o_trazet_limits mb-0">'
                '<thead><tr><th>%s</th><th>%s</th><th class="text-end">%s</th></tr></thead>'
                '<tbody>%s</tbody></table>'
            ) % (_("Product"), _("Trazet Key"), _("Limit"), rows)

    @staticmethod
    def _trazet_format_limit(value):
        if isinstance(value, bool):
            return _("Yes") if value else _("No")
        return escape(value)

    def _compute_trazet_effective_date(self):
        SaleOrder = self.env['sale.order'].sudo()
        for partner in self:
            date = subscription = note = False
            if partner.is_trazet_user and partner._origin:
                date, subscription, note = SaleOrder._get_partner_closest_effective_date(partner._origin)
            partner.trazet_effective_date = date or False
            partner.trazet_effective_subscription_id = subscription or False
            partner.trazet_effective_note = note or False

    def _compute_trazet_grace(self):
        SaleOrder = self.env['sale.order'].sudo()
        # The grace period lives in sale_order_grace.py; stay inert if that
        # part of the module is not loaded.
        has_grace = hasattr(SaleOrder, '_trazet_grace_state')
        for partner in self:
            state = {}
            if has_grace and partner.is_trazet_user and partner._origin:
                state = SaleOrder._trazet_grace_state(partner._origin)
            partner.trazet_grace_available = bool(state.get('eligible') and not state.get('locked'))
            partner.trazet_grace_days = state.get('days') or 0
            partner.trazet_grace_granted_on = state.get('granted_on') or False
            source = state.get('granted_source')
            partner.trazet_grace_source = (
                {'portal': _('Customer portal'), 'backend': _('Billing team')}.get(source, source)
                if source else False)
            partner.trazet_grace_days_granted = state.get('granted_days') or 0
            partner.trazet_grace_expiry = state.get('expiry') or False
            partner.trazet_grace_subscription_id = state.get('subscription') or False

    def _compute_trazet_api_status(self):
        Log = self.env['api.retry.log'].sudo()
        for partner in self:
            origin = partner._origin
            if not origin:
                partner.trazet_api_log_count = 0
                partner.trazet_last_sync = False
                partner.trazet_last_error = False
                continue
            partner.trazet_api_log_count = Log.search_count([('partner_id', '=', origin.id)])
            last_success = Log.search(
                [('partner_id', '=', origin.id), ('state', '=', 'success')],
                order='create_date desc', limit=1)
            last_problem = Log.search(
                [('partner_id', '=', origin.id), ('state', 'in', ('pending', 'failed'))],
                order='create_date desc', limit=1)
            partner.trazet_last_sync = last_success.create_date or False
            if last_problem and (not last_success or last_problem.create_date > last_success.create_date):
                partner.trazet_last_error = last_problem.last_error or _("Call %s", last_problem.state)
            else:
                partner.trazet_last_error = False

    # ------------------------------------------------------------------
    # Actions (TRAZET tab header)
    # ------------------------------------------------------------------

    def _trazet_check_syncable(self):
        self.ensure_one()
        if not self.is_trazet_user:
            raise UserError(_("%s is not a Trazet user.", self.display_name))
        if not self.user_ids:
            raise UserError(_(
                "%s has no portal user, so there is no Trazet account to sync.", self.display_name))

    @staticmethod
    def _trazet_notify(title, message, kind='success'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': kind,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def action_trazet_sync_limits(self):
        """Push the limits computed from all active subscriptions to Trazet -
        the same PATCH /limits call made on confirmation / upsell."""
        self._trazet_check_syncable()
        SaleOrder = self.env['sale.order'].sudo()
        limits = SaleOrder._calculate_trazet_product_limits(self)
        # Tie the API log to a subscription when there is one.
        order = self._trazet_active_subscriptions()[:1] or SaleOrder
        success, error = order._send_trazet_subscription_update(self, limits)
        if not success:
            raise UserError(_("Trazet rejected the limits update: %s", error))
        self.message_post(body=_("Trazet limits synced manually by %(user)s: %(limits)s",
                                 user=self.env.user.name, limits=limits))
        return self._trazet_notify(_("Trazet"), _("Limits synced to Trazet."))

    def action_trazet_sync_effective_date(self):
        """Push the access-valid-until (deactivation) date to Trazet - the same
        call the daily 'Update Trazet Effective Dates' cron makes."""
        self._trazet_check_syncable()
        success, message = self.env['sale.order'].sudo().update_partner_trazet_effective_date(self)
        if not success:
            raise UserError(_("Could not sync the effective date to Trazet: %s", message))
        self.message_post(body=_("Trazet effective date synced manually by %(user)s: %(msg)s",
                                 user=self.env.user.name, msg=message))
        return self._trazet_notify(_("Trazet"), message)

    def action_trazet_grant_grace(self):
        """Backend grant of the once-per-cycle grace period - same entry point as
        the portal button and the subscription form button."""
        self._trazet_check_syncable()
        days = self.env['sale.order'].trazet_grant_partner_grace(self, source='backend')
        return self._trazet_notify(
            _("Trazet Grace Period"), _("%s-day grace period granted and sent to Trazet.", days))

    def action_trazet_view_api_logs(self):
        self.ensure_one()
        return {
            'name': _('Trazet API Logs'),
            'type': 'ir.actions.act_window',
            'res_model': 'api.retry.log',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
