# -*- coding: utf-8 -*-
from odoo import models, fields, api


class FiosDevice(models.Model):
    _name = 'fios.device'
    _description = 'FIOS Device'
    _order = 'name'

    partner_id = fields.Many2one('res.partner', string='Customer', required=True,
                                 ondelete='cascade', index=True)
    name = fields.Char(string='Device / Plate')
    imei = fields.Char(string='IMEI')
    phone = fields.Char(string='Phone')

    # NB: deliberately NOT named `active`. In Odoo a field called `active` is the
    # magic archive flag, so every device FIOS reported as deactivated was created
    # archived and then filtered out of partner.fios_device_ids - which is why only
    # activated devices ever showed up on the contact.
    device_active = fields.Boolean(string='Activated', default=True)

    device_status = fields.Selection([
        ('activated', 'Activated'),
        ('deactivated', 'Deactivated'),
    ], string='Status', compute='_compute_device_status', store=True)

    @api.depends('device_active')
    def _compute_device_status(self):
        for device in self:
            device.device_status = 'activated' if device.device_active else 'deactivated'
