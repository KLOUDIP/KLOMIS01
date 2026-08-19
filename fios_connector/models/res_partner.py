# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only.
import logging

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_REMOVED = "The FIOS Connector is scheduled for removal and no longer contacts the FIOS API."


class ResPartner(models.Model):
    _inherit = 'res.partner'

    active_unit_ids = fields.One2many('active.units', 'partner_id', string='Active Units')
    fios_token = fields.Char(string='FIOS Token', help='Partner token for the FIOS Account')
    fios_fleet_count = fields.Integer(string='FIOS Fleet Count', compute='_compute_fios_fleets')
    active_unit_last_updated = fields.Datetime('Last Updated')
    billing_month = fields.Selection([('January', 'January'),
                                      ('February', 'February'),
                                      ('March', 'March'),
                                      ('April', 'April'),
                                      ('May', 'May'),
                                      ('June', 'June'),
                                      ('July', 'July'),
                                      ('August', 'August'),
                                      ('September', 'September'),
                                      ('October', 'October'),
                                      ('November', 'November'),
                                      ('December', 'December')
                                      ], string="Billing Month")

    def _compute_fios_fleets(self):
        # Real count, no API call - cheap and keeps stat buttons truthful.
        for partner in self:
            partner.fios_fleet_count = self.env['fios.matching.line'].search_count(
                [('match_fios_missing_id.partner_id', '=', partner.id)]
            )

    def action_view_matching_lines(self):
        return {
            'name': 'FIOS Fleets',
            'type': 'ir.actions.act_window',
            'res_model': 'fios.matching.line',
            'view_mode': 'list,form',
            'domain': [('match_fios_missing_id.partner_id', '=', self.id)],
            'target': 'current',
        }

    def get_active_units(self, *args, **kwargs):
        raise UserError(_REMOVED)

    def remove_data(self, *args, **kwargs):
        return False

    def scheduler_for_fios(self, *args, **kwargs):
        # Stub: the daily "FIOS API Call" cron has been failing with
        # INVALID_AUTH_TOKEN since before the upgrade. Kept as a no-op so a
        # surviving ir.cron record does not raise.
        _logger.info("fios_connector shell: scheduler_for_fios is disabled.")
        return True
