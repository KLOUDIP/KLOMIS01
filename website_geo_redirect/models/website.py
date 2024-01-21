# -*- coding: utf-8 -*-
from urllib.parse import urlparse, parse_qs

from odoo import api, models, http


class Website(models.Model):
    _inherit = "website"

    @api.model
    def get_current_website(self, fallback=True):
        res = super(Website, self).get_current_website()
        if self.env.user.has_group('website.group_website_designer'):
            return res
        website = self.get_geo_website(res)
        if website:
            return website
        return res

    def get_geo_website(self, res):
        website_config = self.env['website.redirect.config'].sudo()
        response = http.request._geoip_resolve()
        redirect_site = website_config.search([('website_id', '=', res.id)], limit=1)
        if redirect_site.filtered(lambda x: x.country_group_ids.id == False and x.is_default == False):
            website_id = redirect_site.filtered(lambda x: x.country_group_ids.id == False and x.is_default == False).website_id
            return website_id
        if response:
            country_code = response.get('country_code', False)
            country_group_ids = self.env['res.country'].search([('code', '=', country_code)]).country_group_ids
            redirect_website = website_config.search([('country_group_ids', 'in', country_group_ids.ids)], limit=1)
            if redirect_website:
                if res.id != redirect_website.website_id.id:
                    return redirect_website.website_id
                else:
                    return res
        website = website_config.search([('is_default', '=', True)], limit=1)
        if website:
            return website.website_id
        return res
