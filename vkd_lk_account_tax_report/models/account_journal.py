# -*- coding: utf-8 -*-
from odoo import models, fields


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    is_sri_lankan_taxable = fields.Boolean(
        string='Is Sri Lankan Taxable',
        default=False,
        help='Check this if the journal is for Sri Lankan taxable transactions'
    )