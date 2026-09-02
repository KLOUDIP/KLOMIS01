# -*- coding: utf-8 -*-
import logging
from urllib.parse import urlencode

from odoo import fields, http
from odoo.exceptions import UserError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)


class FiosCustomerPortal(CustomerPortal):

    @staticmethod
    def _grace_portal_enabled():
        return request.env['ir.config_parameter'].sudo().get_param(
            'vkd_fios_api.grace_portal_enabled', '1') in ('1', 'True', 'true')

    @staticmethod
    def _fios_services_redirect(**params):
        return request.redirect('/my/fios-services?%s' % urlencode(params))

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

        grace_days = request.env['fios.provisioning'].sudo()._grace_period_days()
        partner_sudo = partner.sudo()
        return request.render('vkd_fios_signup.portal_my_fios_services', {
            'page_name': 'fios_services',
            'info': info,
            'error': error,
            'is_fios_customer': partner.fios_provision_state == 'active',
            'partner': partner,
            'account_status': partner_sudo.fios_account_status,
            'grace_days': grace_days,
            'grace_available': partner_sudo.fios_grace_available and self._grace_portal_enabled(),
            'grace_expiry': partner_sudo.fios_grace_expiry,
            # Only flag a grace as running while it has not yet expired.
            'grace_active': bool(partner_sudo.fios_grace_expiry
                                 and partner_sudo.fios_grace_expiry >= fields.Date.today()),
            'grace_granted_on': partner_sudo.fios_grace_granted_on,
            'grace_message': kw.get('grace_message'),
            'grace_error': kw.get('grace_error'),
        })

    @http.route(['/my/fios-services/grace'], type='http', auth='user', website=True,
                methods=['POST'], csrf=True)
    def portal_fios_grant_grace(self, **post):
        """Self-service grace period. Guarded server-side: the once-per-cycle and
        account-blocked checks live in fios.provisioning.grant_grace_period, so
        replaying this POST cannot grant a second grace."""
        partner = request.env.user.partner_id
        if not self._grace_portal_enabled():
            return self._fios_services_redirect(
                grace_error="The grace period is not available online. Please contact support.")
        try:
            days = request.env['fios.provisioning'].sudo().grant_grace_period(
                partner, source='portal')
        except UserError as e:
            _logger.info("FIOS portal: grace refused for partner %s: %s", partner.id, e)
            return self._fios_services_redirect(grace_error=str(e))
        except Exception as e:
            _logger.exception("FIOS portal: grace failed for partner %s: %s", partner.id, e)
            return self._fios_services_redirect(
                grace_error="We could not activate your grace period right now. "
                            "Please try again shortly.")

        _logger.info("FIOS portal: %s-day grace period self-granted by partner %s",
                     days, partner.id)
        return self._fios_services_redirect(
            grace_message="Your %s-day grace period is active. Your service has been restored."
                          % days)
