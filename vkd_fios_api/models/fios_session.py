# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class FiosSession(models.Model):
    _name = 'fios.session'
    _description = 'FIOS API Session'
    _order = 'login_time desc'

    sid = fields.Char(string='Session ID (eid)', required=True, index=True)
    tier_id = fields.Many2one('fios.service.tier', string='Service Tier',
                              required=True, ondelete='cascade', index=True)
    auth_user = fields.Char(string='Authenticated User', help='`au` field from the login response')
    login_time = fields.Datetime(string='Login Time', default=fields.Datetime.now)
    last_activity = fields.Datetime(string='Last Activity', default=fields.Datetime.now)
    active = fields.Boolean(string='Active', default=True, index=True)

    @api.model
    def get_active_session(self, tier): 
        return self.search([
            ('active', '=', True),
            ('tier_id', '=', tier.id),
        ], order='login_time desc', limit=1)

    def touch(self):
        for record in self:
            record.last_activity = fields.Datetime.now()

    def invalidate(self):
        for record in self:
            record.active = False
        _logger.info("FIOS session(s) invalidated: %s", self.mapped('sid'))