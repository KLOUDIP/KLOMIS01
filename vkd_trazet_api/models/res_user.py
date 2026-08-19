from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    is_trazet_user = fields.Boolean(string='Is API User?', copy=False, default=False,
                                    help='Is the user allowed to use the API Operations?')

    is_integrator = fields.Boolean(
        string='Is Integrator',
        default=False,
        help='If true, this user is an Integrator and uses separate API token for Trazet'
    )

    @api.model_create_multi
    def create(self, vals_list):
        # overridden to automatically invite user to trazet user sign up
        users = super(ResUsers, self).create(vals_list)

        # Safely check if is_trazet_user exists and is True
        if vals_list and vals_list[0].get('is_trazet_user', False):
            if vals_list[0]['is_trazet_user'] == True:
                users_with_email = users.filtered('email')
                if users_with_email:
                    try:
                        users_with_email.with_context(create_user=True)._action_reset_password(signup_type='signup')
                    except Exception as e:
                        _logger.exception("Failed to send Trazet signup invitation email: %s", str(e))

        return users