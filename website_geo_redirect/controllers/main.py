# -*- coding: utf-8 -*-
from urllib.parse import urlparse, parse_qs
from odoo import http
from odoo.http import request
from odoo.addons.website.controllers.main import Website
from werkzeug.utils import redirect


def are_urls_same(url1, url2):
    # Parse both URLs
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


class WebsiteRegionRedirect(Website):
    @http.route('/', auth='public', website=True)
    def index(self, **kw):
        req = super(WebsiteRegionRedirect, self).index()
        response = request._geoip_resolve()
        host = request.httprequest.host_url
        if response:
            country_code = response.get('country_code', False)
            country_id = request.env['res.country'].search([('code', '=', country_code)])
            redirect_url = request.env['website.redirect.config'].sudo().search([('country_ids', 'in', country_id.ids)], limit=1).website_url
            if redirect_url:
                if not are_urls_same(host, redirect_url):
                    return redirect(redirect_url)
        return req
