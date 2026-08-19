import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        # Store subscription states before posting
        subscription_states = {}
        for move in self:
            if move.invoice_line_ids.subscription_id:
                for subscription in move.invoice_line_ids.subscription_id:
                    subscription_states[subscription.id] = {
                        'old_next_invoice_date': subscription.next_invoice_date,
                        'subscription': subscription
                    }

        result = super()._post(soft=soft)

        # Check if any subscriptions had their next_invoice_date updated
        for subscription_id, state_info in subscription_states.items():
            subscription = state_info['subscription']
            old_date = state_info['old_next_invoice_date']

            # Check if the date actually changed and this is a Trazet user
            if (subscription.next_invoice_date != old_date and
                    subscription.partner_id.is_trazet_user):

                # NEW: Skip Trazet update for free plan subscriptions
                if subscription.is_free_plan:
                    _logger.info(
                        f"Skipping Trazet effective date update for free plan subscription {subscription.name}. "
                        f"Free plan users may not exist in Trazet yet."
                    )
                    subscription.message_post(
                        body=_(
                            "Invoice posted and next invoice date automatically updated to %s. "
                            "Trazet update skipped - Free plan subscription."
                        ) % subscription.next_invoice_date.strftime('%Y-%m-%d'),
                        message_type='comment'
                    )
                    continue  # Skip to next subscription

                try:
                    _logger.info(
                        f"Invoice posting updated next_invoice_date for subscription {subscription.name} "
                        f"from {old_date} to {subscription.next_invoice_date}. "
                        f"Updating Trazet for partner {subscription.partner_id.name}."
                    )

                    # Update Trazet with the new effective date
                    success, message = subscription.update_partner_trazet_effective_date(subscription.partner_id)

                    if success:
                        subscription.message_post(
                            body=_(
                                "Invoice posted and next invoice date automatically updated to %s. "
                                "Trazet has been updated with the new effective date. "
                                "Details: %s"
                            ) % (subscription.next_invoice_date.strftime('%Y-%m-%d'), message),
                            message_type='comment'
                        )

                        _logger.info(
                            f"Successfully updated Trazet for partner {subscription.partner_id.name} "
                            f"after automatic next_invoice_date update: {message}"
                        )
                    else:
                        # Log error but don't block the invoice posting
                        error_message = _(
                            "Invoice posted and next invoice date updated to %s but failed to update Trazet: %s"
                        ) % (subscription.next_invoice_date.strftime('%Y-%m-%d'), message)

                        subscription.message_post(
                            body=error_message,
                            message_type='comment'
                        )

                        _logger.error(
                            f"Failed to update Trazet for partner {subscription.partner_id.name} "
                            f"after automatic next_invoice_date update: {message}"
                        )

                except Exception as e:
                    _logger.error(
                        f"Unexpected error while updating Trazet for subscription {subscription.name} "
                        f"after automatic next_invoice_date update: {str(e)}",
                        exc_info=True
                    )

        return result