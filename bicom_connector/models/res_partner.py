# -*- coding: utf-8 -*-
import uuid
import logging
import requests

from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):

    _inherit = 'res.partner'

    def action_view_call_history(self):
        """View matching lines"""
        call_log_ids = self.env['voip.call'].search([('partner_id', '=', self.id)])
        return_dict = {
            'name': 'Call History',
            'res_model': 'voip.call',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree',
            'view_id': self.env.ref('voip.voip_call_tree_view').id,
            'domain': [('id', 'in', call_log_ids.ids)],
            'target': 'current',
        }
        return return_dict
