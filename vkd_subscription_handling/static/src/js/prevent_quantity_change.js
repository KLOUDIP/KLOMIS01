/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";
import { SaleUpdateLineButton } from "@sale_management/interactions/sale_update_line_button";

patch(SaleUpdateLineButton.prototype, {

    async onQuantityChange(ev, currentTargetEl) {
        if (
            (await this._isRenewalQuotation(this.orderDetail.orderId))
            && (await this._checkComboLine(currentTargetEl.dataset.lineId))
        ) {
            this._showBlockMessage();
            return;
        }
        return super.onQuantityChange(ev, currentTargetEl);
    },

    async onUpdateLineClick(ev, currentTargetEl) {
        if (
            (await this._isRenewalQuotation(this.orderDetail.orderId))
            && (await this._checkComboLine(currentTargetEl.dataset.lineId))
        ) {
            this._showBlockMessage();
            return;
        }
        return super.onUpdateLineClick(ev, currentTargetEl);
    },

    async _checkComboLine(lineId) {
        try {
            const result = await rpc('/web/dataset/call_kw', {
                model: 'sale.order.line',
                method: 'read',
                args: [[parseInt(lineId)], ['linked_line_id', 'combo_item_id', 'product_id']],
                kwargs: {}
            });

            if (result?.length) {
                const line = result[0];
                // Check if line is a combo item (has linked_line_id or combo_item_id)
                return !!(line.linked_line_id || line.combo_item_id);
            }

            return false;
        } catch (error) {
            return false; // Fail-safe: allow update if check fails
        }
    },

    async _isRenewalQuotation(orderId) {
        try {
            const result = await rpc('/web/dataset/call_kw', {
                model: 'sale.order',
                method: 'read',
                args: [[parseInt(orderId)], ['subscription_state']],
                kwargs: {}
            });

            if (result?.length) {
                return result[0].subscription_state === '2_renewal';
            }

            return false;
        } catch (error) {
            return false; // Fail-safe: allow update if check fails
        }
    },

    _showBlockMessage() {
        // Remove any existing alert
        document.querySelector('.combo-block-alert')?.remove();

        const alertEl = document.createElement('div');
        alertEl.className = 'alert alert-warning alert-dismissible fade show combo-block-alert';
        alertEl.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999; max-width: 400px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);';
        alertEl.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="fa fa-exclamation-triangle text-warning me-2"></i>
                <div class="flex-grow-1">
                    <strong>Quantity Change Blocked</strong><br>
                    <small>Combo items cannot be modified in renewal quotations.</small>
                </div>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;

        document.body.appendChild(alertEl);

        setTimeout(() => {
            alertEl.classList.remove('show');
            setTimeout(() => alertEl.remove(), 300);
        }, 5000);
    },
});