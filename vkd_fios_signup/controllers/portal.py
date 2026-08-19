# -*- coding: utf-8 -*-
import logging

from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)


class FiosCustomerPortal(CustomerPortal):

    @http.route(['/my/fios-services'], type='http', auth='user', website=True)
    def portal_my_fios_services(self, **kw):
        partner = request.env.user.partner_id
        info, error = {}, None
        if partner.fios_provision_state == 'active':
            try:
                info = request.env['fios.provisioning'].sudo().get_service_usage(partner)
            except Exception as e:
                _logger.warning("FIOS portal: could not read usage for partner %s: %s", partner.id, e)
                error = "Could not load your FIOS usage right now. Please try again shortly."
        return request.render('vkd_fios_signup.portal_my_fios_services', {
            'page_name': 'fios_services',
            'info': info,
            'error': error,
            'is_fios_customer': partner.fios_provision_state == 'active',
        })