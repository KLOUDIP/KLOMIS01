# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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
    fios_balance = fields.Char(string='FIOS Balance', copy=False, readonly=True)
    fios_services_summary = fields.Text(string='FIOS Services', copy=False, readonly=True,
                                        help='Effective usage / limit per tracked FIOS service.')
    fios_status_synced = fields.Datetime(string='FIOS Status Read At', copy=False, readonly=True)

    fios_service_usage_ids = fields.One2many('fios.service.usage', 'partner_id',
                                             string='FIOS Service Usage', copy=False)
    fios_device_ids = fields.One2many('fios.device', 'partner_id', string='FIOS Devices', copy=False)

    def action_fios_refresh_devices(self):
        self.ensure_one()
        if not self.fios_account_item_id:
            raise UserError(_("This partner has no FIOS account yet."))
        try:
            devices = self.env['fios.provisioning'].list_account_devices(self)
        except Exception as e:
            raise UserError(_("Could not read FIOS devices: %s") % e)
        self.sudo().fios_device_ids.unlink()
        self.env['fios.device'].sudo().create([{
            'partner_id': self.id,
            'name': d.get('name'),
            'imei': d.get('imei'),
            'phone': d.get('phone'),
            'active': d.get('active'),
        } for d in devices])
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('FIOS Devices'),
                'message': _('%s device(s) loaded.') % len(devices),
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