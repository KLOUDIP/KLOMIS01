# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class FiosAccountImport(models.TransientModel):
    _name = 'fios.account.import'
    _description = 'FIOS Account Import'

    tier_id = fields.Many2one('fios.service.tier', string='Service Tier', required=True)
    line_ids = fields.One2many('fios.account.import.line', 'wizard_id', string='Accounts')

    def action_fetch(self):
        self.ensure_one()
        if not self.tier_id:
            raise UserError(_("Select a service tier first."))
        accounts = self.env['fios.provisioning'].list_accounts(self.tier_id)

        self.line_ids.unlink()
        Line = self.env['fios.account.import.line']
        Partner = self.env['res.partner'].sudo()
        for acc in accounts:
            existing = Partner.search([('fios_account_item_id', '=', acc['account_item_id'])], limit=1)
            Line.create({
                'wizard_id': self.id,
                'name': acc.get('name') or '',
                'account_item_id': acc['account_item_id'],
                'resource_id': acc['resource_id'],
                'partner_id': existing.id if existing else False,
                'already_linked': bool(existing),
            })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_import(self):
        self.ensure_one()
        to_import = self.line_ids.filtered(lambda l: l.partner_id and not l.already_linked)
        if not to_import:
            raise UserError(_("Set an Odoo customer on at least one un-linked account."))

        for line in to_import:
            partner = line.partner_id.sudo()
            partner.write({
                'is_fios_user': True,
                'fios_tier_id': self.tier_id.id,
                'fios_resource_id': line.resource_id,
                'fios_account_item_id': line.account_item_id,
                'fios_provision_state': 'active',
                'fios_account_enabled': True,
                'fios_last_error': False,
            })
            _logger.info("FIOS: imported account %s -> partner %s (tier %s)",
                         line.account_item_id, partner.id, self.tier_id.name)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('FIOS Import'),
                'message': _('%s account(s) linked.') % len(to_import),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class FiosAccountImportLine(models.TransientModel):
    _name = 'fios.account.import.line'
    _description = 'FIOS Account Import Line'

    wizard_id = fields.Many2one('fios.account.import', ondelete='cascade')
    name = fields.Char(string='FIOS Account Name', readonly=True)
    account_item_id = fields.Char(string='Account Item ID', readonly=True)
    resource_id = fields.Char(string='Resource ID', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Odoo Customer',
                                 help="Manually match this FIOS account to an Odoo customer.")
    already_linked = fields.Boolean(string='Already Linked', readonly=True)