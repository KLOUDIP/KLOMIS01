# -*- coding: utf-8 -*-
from urllib.parse import urlparse, parse_qs
from werkzeug.utils import redirect

from odoo import models
from odoo.http import request
from odoo import http


def are_urls_same(url1, url2):
    parsed_url1 = urlparse(url1)
    parsed_url2 = urlparse(url2)

    # Normalize the scheme and hostname to lower case
    scheme1, netloc1 = parsed_url1.scheme.lower(), parsed_url1.netloc.lower()
    scheme2, netloc2 = parsed_url2.scheme.lower(), parsed_url2.netloc.lower()

    # Compare schemes and netlocs (domains)
    if scheme1 != scheme2 or netloc1 != netloc2:
        return False

    # Compare paths (empty path is equivalent to '/')
    path1 = parsed_url1.path if parsed_url1.path else '/'
    path2 = parsed_url2.path if parsed_url2.path else '/'
    if path1 != path2:
        return False

    # Compare query parameters (as dictionaries)
    query1 = parse_qs(parsed_url1.query)
    query2 = parse_qs(parsed_url2.query)
    if query1 != query2:
        return False
    return True


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _dispatch(cls, endpoint):
        """Handle SEO-redirected URLs."""

        # if not hasattr(request, "jsonrequest"):
        if request.env.user:
            if not request.env.user.has_group('website.group_website_designer'):
                wsr = get_geo_website()
                if wsr:
                    return redirect(wsr)
        else:
            user_id = request.env.context.get('uid', False)
            if user_id:
                user = request.env['res.users'].browse(user_id)
                if not user.has_group('website.group_website_designer'):
                    wsr = get_geo_website()
                    if wsr:
                        return redirect(wsr)
        return super()._dispatch(endpoint)


def get_geo_website():
    website_config = request.env['website.redirect.config'].sudo()
    response = http.request._geoip_resolve()
    host = http.request.httprequest.host_url
    redirect_site = website_config.search([('website_url', '=', host)], limit=1)

    records = website_config.search([])
    if not records:
        return website_config

    if host.endswith('.odoo.com'):
        return website_config

    if redirect_site.filtered(lambda x: x.country_group_ids.id == False and x.is_default == False):
        website_id = redirect_site.filtered(
            lambda x: x.country_group_ids.id == False and x.is_default == False).website_url
        if are_urls_same(host, website_id):
           return website_config
        return website_id + request.httprequest.full_path[1:]
    if response:
        country_code = response.get('country_code', False)
        country_group_ids = request.env['res.country'].search([('code', '=', country_code)]).country_group_ids
        redirect_website = website_config.search([('country_group_ids', 'in', country_group_ids.ids)], limit=1)
        if redirect_website:
            if not are_urls_same(host, redirect_website.website_url):
                return redirect_website.website_url + request.httprequest.full_path[1:]
            else:
                return website_config
    website = website_config.search([('is_default', '=', True)], limit=1)
    if website:
        if not are_urls_same(host, website.website_url):
            return website.website_url + request.httprequest.full_path[1:]
        else:
            return website_config

    return website_config
