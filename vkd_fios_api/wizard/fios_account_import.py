# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class FiosAccountImport(models.TransientModel):
    _name = 'fios.account.import'
    _description = 'FIOS Account Import'

    tier_id = fields.Many2one('fios.service.tier', string='Service Tier', required=True)

    search_name = fields.Char(
        string='Search',
        help="Search FIOS accounts by name. Leave empty to list every account on the "
             "tier. Wildcards are supported (e.g. 'abans*').")
    hide_linked = fields.Boolean(
        string='Hide Already Linked', default=False,
        help="Hide the accounts that are already matched to an Odoo customer.")

    # Every account fetched from FIOS (the working set).
    line_ids = fields.One2many('fios.account.import.line', 'wizard_id', string='Accounts')
    # The subset currently shown; this is what the form edits. Both point at the
    # same records, so a customer set on a filtered row is kept when the filter
    # changes.
    display_line_ids = fields.Many2many(
        'fios.account.import.line', 'fios_account_import_display_rel',
        'wizard_id', 'line_id', string='Matching Accounts')

    result_count = fields.Integer(string='Results', compute='_compute_result_count')

    @api.depends('display_line_ids', 'line_ids')
    def _compute_result_count(self):
        for wizard in self:
            wizard.result_count = len(wizard.display_line_ids)

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _apply_filter(self):
        """Recompute display_line_ids from the fetched lines and the filter box."""
        self.ensure_one()
        lines = self.line_ids
        term = (self.search_name or '').strip().replace('*', '').lower()
        if term:
            lines = lines.filtered(
                lambda l: term in (l.name or '').lower()
                or term in (l.account_item_id or '')
            )
        if self.hide_linked:
            lines = lines.filtered(lambda l: not l.already_linked)
        self.display_line_ids = [(6, 0, lines.ids)]

    def action_fetch(self):
        """Fetch accounts from FIOS, narrowed by the search term server-side."""
        self.ensure_one()
        if not self.tier_id:
            raise UserError(_("Select a service tier first."))
        accounts = self.env['fios.provisioning'].list_accounts(
            self.tier_id, name_mask=self.search_name)

        self.display_line_ids = [(5, 0, 0)]
        self.line_ids.unlink()
        Line = self.env['fios.account.import.line']
        Partner = self.env['res.partner'].sudo()

        # One query for the whole batch instead of a search per account.
        item_ids = [acc['account_item_id'] for acc in accounts if acc.get('account_item_id')]
        linked = {
            p.fios_account_item_id: p.id
            for p in Partner.search([('fios_account_item_id', 'in', item_ids)])
        }

        created = Line.create([{
            'wizard_id': self.id,
            'name': acc.get('name') or '',
            'account_item_id': acc['account_item_id'],
            'resource_id': acc['resource_id'],
            'partner_id': linked.get(acc['account_item_id'], False),
            'already_linked': acc['account_item_id'] in linked,
        } for acc in accounts]) if accounts else Line

        _logger.info("FIOS: import wizard fetched %s account(s) for tier %s (search %r)",
                     len(created), self.tier_id.name, self.search_name or '*')
        self._apply_filter()
        return self._reopen()

    def action_search(self):
        """Filter the already-fetched list without going back to FIOS.

        This is a button (not an onchange) on purpose: clicking it saves the form
        first, so any customer already picked on a row is kept.
        """
        self.ensure_one()
        if not self.line_ids:
            return self.action_fetch()
        self._apply_filter()
        return self._reopen()

    def action_clear_search(self):
        self.ensure_one()
        self.search_name = False
        self._apply_filter()
        return self._reopen()

    def action_import(self):
        self.ensure_one()
        to_import = self.line_ids.filtered(lambda l: l.partner_id and not l.already_linked)
        if not to_import:
            raise UserError(_("Set an Odoo customer on at least one un-linked account."))

        # Guard against two FIOS accounts being pointed at the same customer in
        # one go - the last write would silently win otherwise.
        seen = {}
        for line in to_import:
            if line.partner_id.id in seen:
                raise UserError(_(
                    "Customer '%(partner)s' is set on more than one FIOS account "
                    "(%(first)s and %(second)s). Each customer can hold one FIOS account."
                ) % {'partner': line.partner_id.display_name,
                     'first': seen[line.partner_id.id],
                     'second': line.account_item_id})
            seen[line.partner_id.id] = line.account_item_id

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
    _order = 'name'

    wizard_id = fields.Many2one('fios.account.import', ondelete='cascade')
    name = fields.Char(string='FIOS Account Name', readonly=True)
    account_item_id = fields.Char(string='Account Item ID', readonly=True)
    resource_id = fields.Char(string='Resource ID', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Odoo Customer',
                                 help="Manually match this FIOS account to an Odoo customer.")
    already_linked = fields.Boolean(string='Already Linked', readonly=True)
