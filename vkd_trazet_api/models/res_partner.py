from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_trazet_user = fields.Boolean(string='Is Trazet User?', copy=False, default=False, help='Is the user allowed to use the API Operations?')
