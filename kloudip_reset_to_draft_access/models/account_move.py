import logging

from odoo import models

_logger = logging.getLogger(__name__)

GROUP = 'kloudip_reset_to_draft_access.group_account_reset_to_draft'


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _reset_to_draft_allowed(self):
        return self.env.user.has_group(GROUP)

    def _is_user_able_to_review(self):
        """ Allow members of the dedicated group to pass the review check.

        Core gates the reset in account.move.write():

            if vals.get('state') == 'draft' and move.checked and not move._is_user_able_to_review():
                raise ValidationError(_("Validated entries can only be changed by your accountant."))

        Side effect: this method also gates writing the 'Reviewed' (checked)
        flag and feeds _compute_checked, so entries posted by these users are
        marked Reviewed, exactly as they are for an accountant.
        """
        if self._reset_to_draft_allowed():
            return True
        return super()._is_user_able_to_review()

    def button_draft(self):
        """ Belt and braces: clear 'Reviewed' before core evaluates the guard.

        This does not depend on where _is_user_able_to_review() sits in the MRO,
        so it works even if another module's override wins. Clearing 'checked'
        is consistent with core behaviour: _compute_checked sets it to False for
        any move that is not posted, so the flag would be dropped anyway.

        Every other protection still applies - hash-secured entries, lock dates
        and cancellation requests are raised by super() / write() as usual.
        """
        if self._reset_to_draft_allowed():
            to_unreview = self.filtered(lambda move: move.checked and move.state in ('posted', 'cancel'))
            if to_unreview:
                _logger.info(
                    "User %s clearing Reviewed flag on %s before reset to draft",
                    self.env.user.login, to_unreview.ids,
                )
                to_unreview.sudo().write({'checked': False})
        return super().button_draft()
