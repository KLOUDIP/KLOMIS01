# -*- coding: utf-8 -*-
from odoo import fields, models


class FiosDevice(models.Model):
    _inherit = 'fios.device'

    # Hiding the IMEI / phone columns in a view does not stop them being read
    # another way (Export, custom filters, group by, RPC). Field-level groups
    # close that for the Billing Team. Tech Team is the group used so the
    # contact FIOS tab keeps working as vkd_fios_api designed it (Tech Team and
    # Administrators see the numbers there); in the FIOS Units report they are
    # further limited to Administrators, since the Tech Team has no access to
    # the report. Every write to these fields (device refresh) runs under sudo.
    imei = fields.Char(groups='vkd_fios_api.group_fios_tech_team')
    phone = fields.Char(groups='vkd_fios_api.group_fios_tech_team')
