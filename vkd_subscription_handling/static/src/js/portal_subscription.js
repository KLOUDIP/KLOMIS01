/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.SubscriptionQuantityDecrease = publicWidget.Widget.extend({
    selector: '#wc-modal-decrease-quantity',
    events: {
        'input .quantity-input': '_onQuantityChange',
        'click .subscription-decrease-quantity-finish': '_onSubmitDecrease',
    },

    /**
     * @override
     */
    start: function () {
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Handle quantity input changes to ensure valid values
     * @private
     */
    _onQuantityChange: function (ev) {
        const input = ev.currentTarget;
        const currentQty = parseFloat(input.dataset.currentQty);
        const trazet_key = input.dataset.trazetKey;
        let newQty = parseFloat(input.value);

        // Special handling for allowExternalAPI and collectPeriod - only allow 0 or 1
        if (trazet_key === 'allowExternalAPI' || trazet_key === 'collectPeriod') {
            if (newQty > 1) {
                newQty = 1;
                this._showProductLimitAlert(trazet_key);
            } else if (newQty < 0) {
                newQty = 0;
            } else if (newQty > 0 && newQty < 1) {
                // Round to nearest valid value (0 or 1)
                newQty = newQty >= 0.5 ? 1 : 0;
            }
        } else {
            // Enforce min/max values for other products
            if (isNaN(newQty) || newQty < 0) {
                newQty = 0;
            } else if (newQty > currentQty) {
                newQty = currentQty;
            }
        }

        // Update input value
        input.value = newQty;

        // Set visual indication for changed values
        if (newQty < currentQty) {
            input.classList.add('border-primary');
        } else {
            input.classList.remove('border-primary');
        }
    },

    /**
     * Show alert for products with quantity limits
     * @private
     */
    _showProductLimitAlert: function (trazet_key) {
        const productName = trazet_key === 'allowExternalAPI' ? 'API Access' : '400 Days History';

        // Remove any existing alert
        const existingAlert = document.querySelector('.product-limit-alert');
        if (existingAlert) {
            existingAlert.remove();
        }

        const alert = document.createElement('div');
        alert.className = 'alert alert-warning alert-dismissible fade show product-limit-alert';
        alert.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999; max-width: 400px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);';
        alert.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="fa fa-info-circle text-warning me-2"></i>
                <div class="flex-grow-1">
                    <strong>${productName} Limit</strong><br>
                    <small>This product can only have a quantity of 1. It's charged per subscription period, not by quantity.</small>
                </div>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;

        document.body.appendChild(alert);

        // Auto-hide after 5 seconds
        setTimeout(() => {
            if (alert.parentNode) {
                alert.classList.remove('show');
                setTimeout(() => alert.remove(), 300);
            }
        }, 5000);
    },

    /**
     * Validate before submitting the decrease form
     * @private
     */
    _onSubmitDecrease: function (ev) {
        const form = ev.currentTarget.closest('form');
        const inputs = form.querySelectorAll('.quantity-input');
        let hasDecrease = false;
        let hasInvalidQuantity = false;

        // Check if at least one product quantity has been decreased
        // and validate special products
        inputs.forEach(input => {
            const currentQty = parseFloat(input.dataset.currentQty);
            const newQty = parseFloat(input.value);
            const trazet_key = input.dataset.trazetKey;

            // Check for quantity changes
            if (newQty < currentQty) {
                hasDecrease = true;
            }

            // Validate allowExternalAPI and collectPeriod can only be 0 or 1
            if ((trazet_key === 'allowExternalAPI' || trazet_key === 'collectPeriod') &&
                newQty !== 0 && newQty !== 1) {
                hasInvalidQuantity = true;
                const productName = trazet_key === 'allowExternalAPI' ? 'API Access' : '365 Days History';
                alert(`${productName} can only have a quantity of 0 (remove) or 1 (keep). Please adjust the quantity.`);
            }
        });

        if (hasInvalidQuantity) {
            ev.preventDefault();
            return false;
        }

        if (!hasDecrease) {
            // Prevent form submission if no quantities were decreased
            ev.preventDefault();
            alert('Please decrease at least one product quantity.');
            return false;
        }

        return true;
    },
});
