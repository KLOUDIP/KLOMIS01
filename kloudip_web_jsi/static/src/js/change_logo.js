/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { HomeMenu } from "@web_enterprise/webclient/home_menu/home_menu";

// We patch the HomeMenu class directly using native Odoo 19 framework utility hooks.
// The template XML defined in manifest handles updating the rendered HTML template.
patch(HomeMenu.prototype, {
    setup() {
        super.setup(...arguments);
        // Custom component mounting logic can be safely added here
    }
});