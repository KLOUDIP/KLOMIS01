# -*- coding: utf-8 -*-

from odoo import models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def create_internal_transfer_payment(self):
        self.ensure_one()
        return self.open_payments_action('transfer', mode='form')
