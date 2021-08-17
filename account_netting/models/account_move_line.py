# -*- coding: utf-8 -*-
from odoo import _, models


class AccountMoveLineCompensate(models.Model):
    _inherit = 'account.move.line'

    def action_compensate_wizard(self):
        ''' Open the account.move.make.netting wizard to pay the selected journal entries.
        :return: An action opening the account.payment.register wizard.
        '''
        return {
            'name': _('Compensate'),
            'res_model': 'account.move.make.netting',
            'view_mode': 'form',
            'context': {
                'active_model': 'account.move.line',
                'active_ids': self.ids,
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }
