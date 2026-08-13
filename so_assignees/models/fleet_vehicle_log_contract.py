# -*- encoding: utf-8 -*-

from odoo import api, models
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class FleetVehicleLogContract(models.Model):
    _inherit = 'fleet.vehicle.log.contract'

    @api.model
    def create(self, vals):
        """Check coordinator is selected on related SO"""
        res = super(FleetVehicleLogContract, self).create(vals)
        if not res.sale_id.coordinator_id:
            raise ValidationError(f'Please, select a coordinator for this sale order - {res.sale_id.name}')
        return res
