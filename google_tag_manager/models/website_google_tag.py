# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    google_gtm_key = fields.Char('Google GTM Key', related='website_id.google_gtm_key', readonly=False)


class InheritWebsite(models.Model):
    _inherit = 'website'

    google_gtm_key = fields.Char('Google GTM Key')
