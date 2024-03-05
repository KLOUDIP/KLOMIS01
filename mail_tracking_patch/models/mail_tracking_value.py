# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import api, fields, models


class MailTracking(models.Model):
    _inherit = 'mail.tracking.value'

    @api.depends('mail_message_id', 'field_id')
    def _compute_field_groups(self):
        for tracking in self:

            if tracking.field_id.model:
                model = self.env[tracking.field_id.model]
            else:
                model = self.env[tracking.mail_message_id.model]
            field = model._fields.get(tracking.field_id.name)
            tracking.field_groups = field.groups if field else 'base.group_system'