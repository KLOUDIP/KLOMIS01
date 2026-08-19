import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { Interaction } from "@web/public/interaction";

/**
 * Lets the customer pick a subscription plan from the quotation portal page.
 *
 * Rewritten from a publicWidget for Odoo 19: the sale portal front end now uses
 * Interactions, `bindService("rpc")` is gone in favour of importing `rpc`
 * directly, and jQuery is no longer used.
 */
export class SaleSubscriptionPackage extends Interaction {
    static selector = ".subscription_packages";

    dynamicContent = {
        "#subscription-package": {
            "t-on-change": this.onChangeSubscriptionPackage.bind(this),
            "t-att-class": () => ({ selected: !!this.selectEl?.value }),
        },
    };

    setup() {
        this.selectEl = this.el.querySelector("#subscription-package");
    }

    async onChangeSubscriptionPackage(ev) {
        ev.preventDefault();
        if (!this.selectEl?.value) {
            return;
        }
        const result = await this.waitFor(
            rpc("/portal/update/sale/subscription/package", {
                subscription_pkg_id: parseInt(this.selectEl.value),
                sale_id: parseInt(this.el.dataset.saleId),
                access_token: this.el.dataset.accessToken,
            })
        );
        if (result?.error) {
            this.services.notification.add(result.error, { type: "danger" });
            return;
        }
        // Prices, taxes and totals are all rendered server side.
        window.location.reload();
    }
}

registry
    .category("public.interactions")
    .add("subscription_packages.sale_subscription_package", SaleSubscriptionPackage);
