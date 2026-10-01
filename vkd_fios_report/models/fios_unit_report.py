# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class VkdFiosUnitReport(models.Model):
    """FIOS Units report: one line per device of a synced FIOS contact.

    A read-only SQL view over fios.device instead of an action on fios.device
    itself. Every internal user can read fios.device (vkd_fios_api grants it so
    the contact FIOS tab works), which would let the Tech Team open the report
    by URL. A model of its own gets its own access rule: Billing Team and
    Administrator only.

    Same "synced contacts only" rule as the FIOS Accounts report.
    """
    _name = 'vkd.fios.unit.report'
    _description = 'FIOS Unit Report'
    _auto = False
    _rec_name = 'name'
    _order = 'partner_id, device_active desc, name'

    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    name = fields.Char(string='Device / Plate', readonly=True)
    # Technical identifiers: FIOS Administrator only. Field-level, so the
    # Billing Team cannot get them through Export, filters or group by either.
    imei = fields.Char(string='IMEI', readonly=True,
                       groups='vkd_fios_api.group_fios_administrator')
    phone = fields.Char(string='Phone', readonly=True,
                        groups='vkd_fios_api.group_fios_administrator')
    device_active = fields.Boolean(string='Activated', readonly=True)
    device_status = fields.Selection([
        ('activated', 'Activated'),
        ('deactivated', 'Inactive'),
    ], string='Status', readonly=True)
    account_status = fields.Selection([
        ('active', 'Active'),
        ('blocked', 'Blocked'),
    ], string='Account Status', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW vkd_fios_unit_report AS (
                SELECT d.id,
                       d.partner_id,
                       d.name,
                       d.imei,
                       d.phone,
                       COALESCE(d.device_active, FALSE) AS device_active,
                       CASE WHEN d.device_active THEN 'activated' ELSE 'deactivated'
                       END AS device_status,
                       p.fios_account_status AS account_status
                  FROM fios_device d
                  JOIN res_partner p ON p.id = d.partner_id
                 WHERE p.active
                   AND p.fios_provision_state = 'active'
                   AND p.fios_account_item_id IS NOT NULL
                   AND p.fios_account_item_id != ''
                   AND p.fios_status_synced IS NOT NULL
                   AND p.fios_account_status IN ('active', 'blocked')
            )
        """)
