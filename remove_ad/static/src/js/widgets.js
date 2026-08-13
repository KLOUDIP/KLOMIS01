/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ThankYouDialog } from "@sign/dialogs/thank_you_dialog";

/**
 * Patch ThankYouDialog to:
 *  1. Remove the Odoo "Sign Up for free" advertisement shown to non-logged-in users.
 *  2. Reload the page on close instead of redirecting to odoo.com/app/sign.
 */
patch(ThankYouDialog.prototype, {
    /**
     * Override: always return false so the sign-up ad block is never rendered.
     * Original: return !user.userId  (shows ad for non-authenticated users)
     */
    get suggestSignUp() {
        return false;
    },

    /**
     * Override: reload the current page on close instead of the default
     * odoo.com redirect that fires when suggestSignUp was true.
     */
    onClickClose() {
        if (this.env.isSmall !== undefined && !this.suggestSignUp) {
            // Fall through to normal backend/frontend close logic
            return super.onClickClose(...arguments);
        }
        window.location.reload();
    },
});