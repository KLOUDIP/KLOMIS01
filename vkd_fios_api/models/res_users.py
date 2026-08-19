# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    is_fios_user = fields.Boolean(
        string='Is FIOS User?',
        copy=False,
        default=False,
        help='Is this user a FIOS-provisioned customer?',
    )

    @api.model
    def upsert_fios_user(self, name, email, phone=None, org_name=None, country_id=None, password=None):
        email = (email or '').strip().lower()
        if not email:
            raise ValueError("email is required to upsert a FIOS user")

        Partner = self.env['res.partner'].sudo()
        user = self.sudo().search([('login', '=', email)], limit=1)

        partner_vals = {'name': name, 'is_fios_user': True}
        if phone:
            partner_vals['phone'] = phone
        if country_id:
            partner_vals['country_id'] = country_id

        # Registration marks the partner 'registered' (Odoo user exists, but no
        # FIOS account yet - that is provisioned at purchase under the product's
        # tier). Only bump a not-yet-started partner; never downgrade one that is
        # already provisioning/active.
        def _with_reg(vals, current_state):
            vals = dict(vals)
            if current_state in ('not_started', False):
                vals['fios_provision_state'] = 'registered'
            return vals

        if user:
            # Existing login (may already be a Trazet user) - update + OR-in flag.
            user.partner_id.write(_with_reg(partner_vals, user.partner_id.fios_provision_state))
            user_vals = {'is_fios_user': True}
            if password:
                user_vals['password'] = password
            user.write(user_vals)
            # Stash the FIOS password for purchase-time provisioning.
            if password:
                user.partner_id.fios_store_pending_password(password)
            return user

        # Reuse a bare partner with this email if one exists, else create it.
        partner = Partner.search([('email', '=', email)], limit=1)
        if partner:
            partner.write(_with_reg(partner_vals, partner.fios_provision_state))
        else:
            partner = Partner.create({
                **partner_vals,
                'email': email,
                'company_name': org_name or False,
                'customer_rank': 1,
                'is_company': False,
                'fios_provision_state': 'registered',
            })

        portal_group = self.env.ref('base.group_portal')
        user_vals = {
            'name': name,
            'login': email,
            'email': email,
            'partner_id': partner.id,
            'group_ids': [(6, 0, [portal_group.id])],
            'active': True,
            'is_fios_user': True,
        }
        if password:
            user_vals['password'] = password
        user = self.sudo().create(user_vals)
        # Stash the FIOS password for purchase-time provisioning.
        if password:
            partner.fios_store_pending_password(password)
        _logger.info("FIOS: upserted Odoo user %s (partner %s) for %s", user.id, partner.id, email)
        return user