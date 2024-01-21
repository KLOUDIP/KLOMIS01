# -*- coding: utf-8 -*-
from odoo import models, fields


class WebsiteRedirectConfig(models.Model):
    _name = 'website.redirect.config'
    _description = 'Website Redirect Configuration'

    website_id = fields.Many2one('website', string="Website", required=True)
    country_ids = fields.Many2many('res.country', string='Countries')
    country_group_ids = fields.Many2many('res.country.group', string="Region")
    website_url = fields.Char('Website URL', required=True)
    is_default = fields.Boolean(string="Is Default?")

