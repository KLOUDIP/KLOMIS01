from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _is_user_able_to_review(self):
        """ Allow members of the dedicated group to reset posted entries to draft.

        Core gates the reset in account.move.write():

            if vals.get('state') == 'draft' and move.checked and not move._is_user_able_to_review():
                raise ValidationError(_("Validated entries can only be changed by your accountant."))

        Granting the group here is equivalent, for this single check, to granting
        the Accounting Administrator role - without any of that role's other
        rights and without Settings access.

        Side effect to be aware of: this method also gates writing the 'Reviewed'
        (checked) flag and feeds _compute_checked, so entries posted by these
        users will be marked Reviewed, exactly as they are for an accountant.
        """
        if self.env.user.has_group('kloudip_reset_to_draft_access.group_account_reset_to_draft'):
            return True
        return super()._is_user_able_to_review()
