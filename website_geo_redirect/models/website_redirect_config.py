# models/website_redirect_config.py
from odoo import models, fields

class WebsiteRedirectConfig(models.Model):
    _name = 'website.redirect.config'
    _description = 'Website Redirect Configuration'

    website_id = fields.Many2one('website', string="Website")
    country_ids = fields.Many2many('res.country', string='Countries', required=True)
    website_url = fields.Char('Website URL', required=True)

