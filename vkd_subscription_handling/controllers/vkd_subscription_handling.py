# -*- coding: utf-8 -*-

import json
from odoo import http, _
from odoo.http import request
from odoo.addons.sale_subscription.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError, MissingError, ValidationError
import werkzeug
import logging

_logger = logging.getLogger(__name__)

# (trazet_product_key, FontAwesome icon class, display label)
TRAZET_SERVICE_DISPLAY = [
    ('users', 'fa-user', 'Users'),
    ('devices', 'fa-microchip', 'Devices'),
    ('devicesGroups', 'fa-object-group', 'Device Groups'),
    ('geofences', 'fa-map-marker', 'Geofences'),
    ('notifications', 'fa-bell', 'Notifications'),
    ('drivers', 'fa-id-card', 'Drivers'),
    ('commands', 'fa-terminal', 'Commands'),
    ('collectPeriod', 'fa-calendar', 'Period to Collect Data'),
    ('allowExternalAPI', 'fa-plug', 'Allow External API'),
]


class SubscriptionPortal(CustomerPortal):

    def _prepare_trazet_services(self, limits):
        services = []
        for key, icon, label in TRAZET_SERVICE_DISPLAY:
            if key not in limits:
                continue
            value = limits[key]
            if key == 'collectPeriod':
                display_value = _("%s Days") % value
            elif key == 'allowExternalAPI':
                display_value = _("Yes") if value else _("No")
            else:
                display_value = value
            services.append({'icon': icon, 'label': label, 'value': display_value})
        return services

    @http.route(['/my/services'], type='http', auth='user', website=True)
    def portal_my_trazet_services(self, **kw):
        partner = request.env.user.partner_id
        limits = {}
        if partner.is_trazet_user:
            limits = request.env['sale.order'].sudo()._calculate_trazet_product_limits(partner=partner)

        values = {
            'page_name': 'trazet_services',
            'services': self._prepare_trazet_services(limits),
        }
        return request.render('vkd_subscription_handling.portal_my_trazet_services', values)

    @http.route(['/my/subscriptions/<int:order_id>/decrease'], type='http', auth="public")
    def subscription_portal_decrease(self, order_id, access_token=None, **kw):
        order_sudo, redirection = self._get_subscription(access_token, order_id)
        if redirection:
            return redirection

        # Only allow decrease for in-progress subscriptions
        if order_sudo.subscription_state not in ['3_progress', '4_paused']:
            return request.redirect(order_sudo.get_portal_url())

        decrease_action = order_sudo.prepare_decrease_order()
        if decrease_action:
            decrease_order = request.env['sale.order'].sudo().browse(decrease_action.get('res_id'))
            decrease_order.action_quotation_sent()
            return request.redirect(decrease_order.get_portal_url())

        return request.redirect(order_sudo.get_portal_url())

    @http.route(['/my/subscriptions/<int:order_id>/decrease_quantity'], type='http', auth="public", website=True,
                methods=['POST'], csrf=True)
    def decrease_subscription_quantity(self, order_id, access_token=None, **kw):
        """Process quantity decrease directly - CSRF protection enabled"""
        try:
            order_sudo, redirection = self._get_subscription(access_token, order_id)
            if redirection:
                return redirection

            # Only allow decrease for in-progress subscriptions
            if order_sudo.subscription_state not in ['3_progress', '4_paused']:
                return request.redirect(order_sudo.get_portal_url())

            # Process form data - extract line_id and new quantity
            decrease_lines = {}
            for key, value in kw.items():
                if key.startswith('line_qty_'):
                    try:
                        line_id = key.replace('line_qty_', '')
                        qty = float(value)
                        # Validate the line exists and belongs to this subscription
                        line = request.env['sale.order.line'].sudo().browse(int(line_id))
                        if line.exists() and line.order_id.id == order_sudo.id:
                            # Validate special products
                            trazet_key = line.product_id.product_tmpl_id.trazet_product_key
                            if trazet_key in ['allowExternalAPI', 'collectPeriod']:
                                if qty != 0 and qty != 1:
                                    product_name = 'API Access' if trazet_key == 'allowExternalAPI' else '400 Days History'
                                    error_msg = f"{product_name} can only have a quantity of 0 (remove) or 1 (keep). You entered {qty}."
                                    return request.redirect(
                                        order_sudo.get_portal_url() + f"&error=invalid_quantity&message={werkzeug.urls.url_quote(error_msg)}"
                                    )
                            decrease_lines[line_id] = qty
                    except (ValueError, TypeError):
                        _logger.warning(f"Invalid quantity value for line {key}: {value}")
                        continue

            if decrease_lines:
                try:
                    is_fios = order_sudo._is_fios_subscription()

                    if is_fios:
                        # Block a decrease that would drop a FIOS service limit below
                        # what the customer is currently using (e.g. reduce Users to 2
                        # while 3 are active).
                        projected = order_sudo._calculate_projected_fios_limits_after_decrease(
                            decrease_lines)
                        ok, usage_err = order_sudo._fios_check_usage_allows(
                            order_sudo.partner_id, projected)
                        if not ok:
                            return request.redirect(
                                order_sudo.get_portal_url()
                                + f"&error=fios_usage&message={werkzeug.urls.url_quote(usage_err)}")
                    else:
                        # FIOS subscriptions provision on FIOS, not Trazet: skip the
                        # Trazet validation entirely.
                        product_limits = order_sudo._calculate_projected_trazet_limits_after_decrease(
                            decrease_lines)

                        if not product_limits:
                            return request.redirect(order_sudo.get_portal_url() + "&error=no_valid_products")

                        success, error_msg = order_sudo._send_trazet_subscription_update(
                            partner=order_sudo.partner_id,
                            product_limits=product_limits)

                        if not success:
                            return request.redirect(order_sudo.get_portal_url() + f"&error=trazet&message={werkzeug.urls.url_quote(error_msg)}")

                    result = order_sudo.sudo()._confirm_quantity_decrease(decrease_lines)

                    if result:
                        order_sudo.sudo().write({'is_quantity_decrease': True})
                        # Push the reduced limits to FIOS (the decrease doesn't go
                        # through action_confirm/set_close, so sync explicitly).
                        if is_fios and hasattr(order_sudo, '_sync_fios_limits'):
                            order_sudo.sudo()._sync_fios_limits(order_sudo.partner_id)
                        return request.redirect(order_sudo.get_portal_url() + "&success=decrease")
                    else:
                        return request.redirect(order_sudo.get_portal_url() + "&error=no_changes")

                except Exception as e:
                    _logger.exception("Error during product limit processing: %s", str(e))
                    return request.redirect(order_sudo.get_portal_url() + "&error=trazet_exception")
            else:
                return request.redirect(order_sudo.get_portal_url() + "&error=no_lines")

        except Exception as e:
            _logger.exception("Error processing quantity decrease: %s", str(e))
            return request.redirect(f"/my/subscriptions/{order_id}&error=processing")


    @http.route(['/my/subscriptions/<int:order_id>/close', '/my/subscription/<int:order_id>/close'],
                type='http', methods=["POST"], auth="public", website=True)
    def close_account(self, order_id, access_token=None, **kw):
        """Override to add Trazet validation before closing subscription"""
        order_sudo, redirection = self._get_subscription(access_token, order_id)
        if redirection:
            return redirection

        if order_sudo.plan_id.user_closable:
            close_reason = request.env['sale.order.close.reason'].browse(int(kw.get('close_reason_id')))
            if close_reason:
                # Check if this is a Trazet user and validate before closing.
                # FIOS subscriptions are handled by set_close (FIOS side), so skip
                # Trazet validation for them.
                if (order_sudo.is_subscription and
                        order_sudo.subscription_state in ['3_progress', '4_paused'] and
                        order_sudo.partner_id.is_trazet_user and
                        not order_sudo._is_fios_subscription()):

                    try:
                        # Calculate what the limits would be after closing this subscription
                        projected_limits = order_sudo._calculate_projected_trazet_limits_after_close()

                        # Check with Trazet API before proceeding
                        success, error_msg = order_sudo._send_trazet_subscription_update(
                            partner=order_sudo.partner_id,
                            product_limits=projected_limits
                        )

                        if not success:
                            # If Trazet API returns an error, redirect with error message
                            return request.redirect(
                                f'/my/subscriptions/{order_id}?access_token={access_token}&error=trazet&message={error_msg}'
                            )

                    except Exception as e:
                        _logger.exception("Error validating subscription close with Trazet: %s", str(e))
                        return request.redirect(
                            f'/my/subscriptions/{order_id}?access_token={access_token}&error=trazet_exception'
                        )

                # If Trazet validation passes or not applicable, proceed with closing
                if kw.get('closing_text'):
                    order_sudo.message_post(body=_('Closing text: %s', kw.get('closing_text')))
                order_sudo.with_context(allow_future_end_date=True).set_close(close_reason_id=close_reason.id)

        return request.redirect(f'/my/subscriptions/{order_id}?access_token={access_token}')