# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class FleetVehicleLogContract(models.Model):
    _inherit = 'fleet.vehicle.log.contract'

    fios_active_unit_available = fields.Boolean('FIOS Active Unit Available')

    @api.onchange('partner_id')
    def _onchange_billing_contract(self):
        subscription_count = len(self.env['sale.subscription'].search([('partner_id', '=', self.partner_id.id)]))
        if subscription_count == 0:
            raise ValidationError(_('No subscriptions are available for the selected billing contact! \nYou need to select a billing contact which contains subscriptions.'))