# -*- coding: utf-8 -*-
import logging

from odoo import models, fields

_logger = logging.getLogger(__name__)


class FiosServiceTier(models.Model):
    _name = 'fios.service.tier'
    _description = 'FIOS Service Tier'
    _order = 'sequence, name'

    name = fields.Char(required=True, help="e.g. FIOS, FIOS Lite, FIOS Premium")
    code = fields.Char(required=True, help="Short unique code, e.g. fios / lite / premium")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    base_url = fields.Char(string='Base URL', required=True,
                           default='https://fios-api.kloudip.com')
    token = fields.Char(string='API Token', required=True,
                        help="Long-lived FIOS login token for this tier.")
    creator_id = fields.Char(string='Creator ID', required=True,
                             help="Top-level creator user id for this tier.")
    plan_code = fields.Char(string='Billing Plan Code', required=True,
                            help="FIOS billing plan passed to account/create_account (e.g. kloudip3).")

    _code_uniq = models.Constraint(
        'unique(code)',
        "The tier code must be unique.",
    )