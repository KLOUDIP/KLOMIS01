# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http, _
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.mail import _message_post_helper

import binascii


class CustomerPortalW(CustomerPortal):
    @http.route(['/my/sheet/<int:sheet_id>/worksheet/',
                 '/my/sheet/<int:sheet_id>/worksheet/<string:source>'], type='http', auth="public", website=True)
    def portal_my_worksheet_id(self, sheet_id, access_token=None, source=False, report_type=None, download=False, message=False, **kw):

        try:
            task_sudo = self._document_check_access('worksheet.template.line', sheet_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        if report_type in ('html', 'pdf', 'text'):
            return self._show_report(model=task_sudo, report_type=report_type, report_ref='field_service_worksheet_template.task_custom_report_template', download=download)

        worksheet_map = {}
        if task_sudo.template_id:
            x_model = task_sudo.template_id.model_id.model
            worksheet = request.env[x_model].sudo().search([('x_studio_line_id', '=', task_sudo.id)], limit=1, order="create_date DESC")  # take the last one
            worksheet_map[task_sudo.id] = worksheet

        return request.render("field_service_worksheet_template.portal_my_worksheet_new", {'worksheet_map': worksheet_map, 'sheet': task_sudo, 'message': message, 'source': source})


    @http.route(['/my/sheet/<int:sheet_id>/worksheet/customer_sign/<string:source>'], type='json', auth="public", website=True)
    def portal_worksheet_customer_sign(self, sheet_id, access_token=None, source=False, name=None, signature=None):
        # get from query string if not on json param
        access_token = access_token or request.httprequest.args.get('access_token')
        try:
            task_sudo = self._document_check_access('worksheet.template.line', sheet_id, access_token)
        except (AccessError, MissingError):
            return {'error': _('Invalid Task.')}

        # if not task_sudo.has_to_be_signed():
        #     return {'error': _('The worksheet is not in a state requiring customer signature.')}
        if not signature:
            return {'error': _('Signature is missing.')}

        try:
            task_sudo.write({
                'customer_signature': signature,
                'customer_signed_by': name,
            })

        except (TypeError, binascii.Error):
            return {'error': _('Invalid signature data.')}

        # try:
        #     task_sudo.write({
        #         'technician_signature': signature,
        #         'technician_signed_by': name,
        #     })
        #
        # except (TypeError, binascii.Error):
        #     return {'error': _('Invalid signature data.')}

        # _message_post_helper(
        #     'project.task', task_sudo.id, _('Task signed by %s') % (name,),
        #     **({'token': access_token} if access_token else {}))

        query_string = '&message=sign_ok'
        return {
            'force_refresh': True,
            'redirect_url': task_sudo.get_portal_url(suffix='/worksheet/%s' % source, query_string=query_string),
        }

    @http.route(['/my/sheet/<int:sheet_id>/worksheet/technician_sign/<string:source>'], type='json', auth="public",
                website=True)
    def portal_worksheet_technician_sign(self, sheet_id, access_token=None, source=False, name=None, signature=None):
        # get from query string if not on json param
        access_token = access_token or request.httprequest.args.get('access_token')
        try:
            task_sudo = self._document_check_access('worksheet.template.line', sheet_id, access_token)
        except (AccessError, MissingError):
            return {'error': _('Invalid Task.')}

        # if not task_sudo.has_to_be_signed():
        #     return {'error': _('The worksheet is not in a state requiring customer signature.')}
        if not signature:
            return {'error': _('Signature is missing.')}

        # try:
        #     task_sudo.write({
        #         'customer_signature': signature,
        #         'customer_signed_by': name,
        #     })
        #
        # except (TypeError, binascii.Error):
        #     return {'error': _('Invalid signature data.')}

        try:
            task_sudo.write({
                'technician_signature': signature,
                'technician_signed_by': name,
            })

        except (TypeError, binascii.Error):
            return {'error': _('Invalid signature data.')}

        # _message_post_helper(
        #     'project.task', task_sudo.id, _('Task signed by %s') % (name,),
        #     **({'token': access_token} if access_token else {}))

        query_string = '&message=sign_ok'
        return {
            'force_refresh': True,
            'redirect_url': task_sudo.get_portal_url(suffix='/worksheet/%s' % source, query_string=query_string),
        }
