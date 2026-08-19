import logging
import requests
import json
import pytz
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_free_plan = fields.Boolean(
        string='Is Free Plan Subscription',
        default=False,
        copy=False,
        help='Technical field to identify free plan subscriptions created automatically. '
             'Used to skip API retry log creation for free plans.'
    )

    grace_period_days = fields.Selection([
        ('3', '3 Days'),
        ('7', '7 Days'),
        ('10', '10 Days'),
        ('14', '14 Days'),
        ('21', '21 Days'),
    ], string='Grace Period', help='Grace period before deactivation in Trazet')

    api_retry_log_ids = fields.One2many('api.retry.log', 'sale_order_id', string='API Retry Logs')

    api_retry_log_count = fields.Integer(
        string='API Logs Count',
        compute='_compute_api_retry_log_count',
        help='Number of API retry logs for this subscription'
    )

    @api.depends('api_retry_log_ids')
    def _compute_api_retry_log_count(self):
        for order in self:
            order.api_retry_log_count = len(order.api_retry_log_ids)

    def action_view_api_retry_logs(self):
        self.ensure_one()

        return {
            'name': 'API Logs',
            'type': 'ir.actions.act_window',
            'res_model': 'api.retry.log',
            'view_mode': 'list,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {
                'default_sale_order_id': self.id,
                'search_default_group_state': 1,  # Group by state by default
            },
            'help': """
                <p class="o_view_nocontent_smiling_face">
                    No API logs found for this subscription
                </p>
                <p>
                    API logs track all Trazet API calls (successful and failed) for this subscription.
                </p>
            """
        }

    def _get_trazet_api_config(self, user=None):
        config_param = self.env['ir.config_parameter'].sudo()
        trazet_api_url = config_param.get_param('vkd_trazet_api.trazet_api_url')
        # trazet_auth_token = config_param.get_param('vkd_trazet_api.trazet_auth_token')

        if user and user.is_integrator:
            trazet_auth_token = self.env['ir.config_parameter'].sudo().get_param(
                'vkd_trazet_api.trazet_integrator_auth_token'
            )
            _logger.info(f"Using INTEGRATOR token for user {user.login} (ID: {user.id})")
        else:
            trazet_auth_token = self.env['ir.config_parameter'].sudo().get_param(
                'vkd_trazet_api.trazet_auth_token'
            )
            if user:
                _logger.info(f"Using ORGANIZATION token for user {user.login} (ID: {user.id})")

        return trazet_api_url, trazet_auth_token

    def _is_free_plan_subscription(self):
        self.ensure_one()
        if not self.is_subscription:
            return False

        # Check if all recurring products are free plan
        recurring_lines = self.order_line.filtered(lambda l: l.recurring_invoice)
        if not recurring_lines:
            return False

        return all(
            line.product_id.product_tmpl_id.is_free_plan
            for line in recurring_lines
        )

    def _is_fios_subscription(self):
        """True when the subscription carries FIOS products (fios_service). Such
        subscriptions are provisioned on FIOS, not Trazet, so the Trazet sync must
        skip them. Defensive: vkd_trazet_api does not depend on vkd_fios_api, so we
        only look at fios_service when the field is installed."""
        self.ensure_one()
        if 'fios_service' not in self.env['product.template']._fields:
            return False
        return any(
            line.recurring_invoice and line.product_id.product_tmpl_id.fios_service
            for line in self.order_line
        )

    def _send_trazet_subscription_update(self, partner, product_limits):
        if not partner.user_ids.id:
            _logger.warning(
                f"Cannot send subscription update to Trazet for partner {partner.name}: No linked user found.")
            return True, None

        trazet_api_url, trazet_auth_token = self._get_trazet_api_config(partner.user_ids[0])

        if not trazet_api_url or not trazet_auth_token:
            _logger.error(
                "Trazet API URL or Auth Token not configured in Odoo system parameters.")
            return False, _("Trazet API configuration is missing. Please contact support.")

        user_id = partner.user_ids[0].id
        url = f"{trazet_api_url}/api/v2/odoo/{partner.user_ids.id}/limits"
        headers = {
            'Content-Type': 'application/json',
            'Trazet-Auth': trazet_auth_token
        }

        try:
            _logger.info(
                f"Sending subscription update to Trazet for partner {partner.name} (User ID: {user_id}). "
                f"Payload: {product_limits}")

            response = requests.patch(url, headers=headers, data=json.dumps(product_limits))

            if response.status_code == 200:
                _logger.info(
                    f"Successfully sent subscription update to Trazet for partner {partner.name}")

                # Log successful API call
                try:
                    response_text = response.text
                except:
                    response_text = 'Success (no response body)'

                self.env['api.retry.log'].create_success_log(
                    api_endpoint='subscription_update',
                    url=url,
                    headers=headers,
                    payload=product_limits,
                    partner=partner,
                    sale_order=self,
                    response_status=response.status_code,
                    response_data=response_text,
                    message=f"Successfully sent subscription update for partner {partner.name}"
                )

                return True, None
            else:
                # Handle error response
                try:
                    error_data = response.json()
                    error_message = error_data.get('message', 'Unknown error')
                    _logger.error(
                        f"Trazet API error for partner {partner.name}: {error_message}")
                    self._create_retry_log('subscription_update', url, headers, product_limits, partner, str(error_message))
                    return False, error_message
                except:
                    _logger.error(
                        f"Trazet API error for partner {partner.name}: Status {response.status_code}")
                    return False, _("Failed to update subscription limits in Trazet.")

        except requests.exceptions.Timeout:
            error_msg = _("Connection timeout. Please try again.")
            _logger.error(f"Timeout when updating Trazet for partner {partner.name}")
            # CREATE RETRY LOG FOR TIMEOUT
            self._create_retry_log('subscription_update', url, headers, product_limits, partner, str(error_msg))
            return False, error_msg
        except requests.exceptions.RequestException as e:
            error_msg = _("Failed to connect to Trazet service.")
            _logger.error(
                f"Failed to send subscription update to Trazet for partner {partner.name}: {e}")
            self._create_retry_log('subscription_update', url, headers, product_limits, partner, str(e))
            return False, error_msg

    def _calculate_trazet_product_limits(self, partner=None):
        """
        Calculate final product limits for Trazet based on ALL active subscriptions for the partner
        :param partner: Partner to calculate limits for. If None, use self.partner_id
        :return: Dictionary with Trazet product keys and total quantities
        """
        if not partner:
            self.ensure_one()
            partner = self.partner_id

        # Find ALL active subscriptions for this partner (including the current one if it's active)
        active_subscriptions = self.env['sale.order'].search([
            ('partner_id', '=', partner.id),
            ('is_subscription', '=', True),
            ('subscription_state', 'in', ['3_progress', '4_paused']),
            ('state', '=', 'sale')
        ])

        # If we're calculating for a new subscription being confirmed, include it
        if (self.is_subscription and
                self.state in ['draft', 'sent'] and
                self.partner_id.id == partner.id):
            active_subscriptions |= self

        product_limits = {}

        for subscription in active_subscriptions:
            # Get all recurring subscription lines (excluding combo items and display lines)
            subscription_lines = subscription.order_line.filtered(
                lambda l: l.recurring_invoice and l.product_id.trazet_product_key)

            for line in subscription_lines:
                trazet_key = line.product_id.trazet_product_key
                if trazet_key:
                    # For combo products, use the main combo line quantity
                    if line.product_id.type == 'combo':
                        total_qty = line.product_uom_qty
                    else:
                        total_qty = line.product_uom_qty

                    # Accumulate quantities for the same Trazet key across ALL subscriptions
                    if trazet_key in product_limits:
                        product_limits[trazet_key] += int(total_qty)
                    else:
                        product_limits[trazet_key] = int(total_qty)

        # Apply Trazet-specific business logic after calculating base quantities
        final_product_limits = {}
        for trazet_key, quantity in product_limits.items():
            if trazet_key == 'users':
                # Special handling: Trazet should always have 1 more user than Odoo
                final_product_limits['users'] = quantity + 1
                _logger.info(
                    f"Trazet users adjustment: Odoo has {quantity} users, sending {quantity + 1} to Trazet as 'user'")

            elif trazet_key == 'allowExternalAPI':
                # Special handling: API Access is a boolean feature, not a quantity
                # CRITICAL: Check if quantity > 0, not just if key exists!
                if quantity > 0:
                    final_product_limits['allowExternalAPI'] = True
                    _logger.info(f"Trazet API Access: Sending allowExternalAPI as true (quantity: {quantity})")
                else:
                    final_product_limits['allowExternalAPI'] = False
                    _logger.info(f"Trazet API Access: Sending allowExternalAPI as false (quantity is 0)")

            elif trazet_key == 'collectPeriod':
                # Special handling: 400 Days History
                # CRITICAL: Check if quantity > 0, not just if key exists!
                if quantity > 0:
                    final_product_limits['collectPeriod'] = 365
                    _logger.info(f"Trazet collectPeriod: Product active, sending 365 (quantity: {quantity})")
                else:
                    final_product_limits['collectPeriod'] = 90
                    _logger.info(f"Trazet collectPeriod: Product removed, sending default 90 (quantity is 0)")

            else:
                # For all other product keys, use the calculated quantity as-is
                final_product_limits[trazet_key] = quantity

        # Ensure collectPeriod is always sent (default 90 if not in order)
        if 'collectPeriod' not in final_product_limits:
            final_product_limits['collectPeriod'] = 90
            _logger.info(f"Trazet collectPeriod: Product not in order, sending default 90")

        # Ensure allowExternalAPI is always sent (default false if not in order)
        if 'allowExternalAPI' not in final_product_limits:
            final_product_limits['allowExternalAPI'] = False
            _logger.info(f"Trazet API Access: Product not in order, sending false")

        _logger.info(
            f"Sending subscription update to Trazet for partner {partner.name} "
            f"Original payload: {product_limits}, Final payload: {final_product_limits}")

        return final_product_limits

    def update_existing_subscriptions(self):
        """
        Override to send final quantities to Trazet after subscription changes.
        This method is called when confirming upsell orders to update main subscription.
        """
        create_values, update_values = super().update_existing_subscriptions()

        # Process each subscription that was updated
        for order in self:
            if order.subscription_state == '7_upsell' and order.subscription_id:
                main_subscription = order.subscription_id

                # Skip FIOS subscriptions - they sync to FIOS, not Trazet.
                if main_subscription._is_fios_subscription():
                    _logger.info(
                        "Skipping Trazet upsell sync for FIOS subscription %s", main_subscription.name)
                    continue

                # Skip API calls for free plan subscriptions
                if main_subscription._is_free_plan_subscription():
                    _logger.info(
                        f"Skipping Trazet API call for free plan upsell on subscription {main_subscription.name}"
                    )
                    main_subscription.message_post(
                        body=_("Trazet API call skipped for upsell - Free plan subscription"),
                        message_type='comment'
                    )
                    continue

                try:
                    product_limits = main_subscription._calculate_trazet_product_limits(
                        main_subscription.partner_id)
                    if product_limits:
                        # Send to Trazet
                        success, error_msg = main_subscription._send_trazet_subscription_update(
                            main_subscription.partner_id,
                            product_limits
                        )

                        if success:
                            # Success - log for tracking
                            main_subscription.message_post(
                                body=_(
                                    "Subscription limits successfully synced to Trazet after upsell: %s") % product_limits,
                                message_type='comment'
                            )
                            order.message_post(
                                body=_("Upsell changes synced to Trazet successfully: %s") % product_limits,
                                message_type='comment'
                            )
                        else:
                            # Log the error but don't block the upsell process
                            _logger.error(
                                f"Failed to sync upsell changes to Trazet for {main_subscription.partner_id.name}: {error_msg}")

                            # Post messages on both orders for tracking
                            error_message = _("Warning: Failed to sync upsell changes to Trazet: %s") % error_msg
                            main_subscription.message_post(
                                body=error_message,
                                message_type='comment'
                            )
                            order.message_post(
                                body=error_message,
                                message_type='comment'
                            )

                except Exception as e:
                    _logger.error(f"Unexpected error while syncing upsell to Trazet: {e}", exc_info=True)
                    # Don't raise exception to avoid breaking upsell flow
                    error_message = _("Error syncing upsell to Trazet: %s") % str(e)
                    main_subscription.message_post(
                        body=error_message,
                        message_type='comment'
                    )
                    order.message_post(
                        body=error_message,
                        message_type='comment'
                    )

        return create_values, update_values

    def action_confirm(self):
        """Override to send total subscription limits to Trazet when subscription is confirmed
        and close any existing free plan subscriptions when a paid subscription is confirmed
        """

        # Store subscriptions that need to check for free plan closure
        subscriptions_to_check = []

        # CRITICAL FIX: Skip free plan closure logic if this is an automatic free subscription creation
        skip_closure = self.env.context.get('skip_free_plan_closure')

        if not skip_closure:
            for order in self:
                if (order.is_subscription and
                        order.partner_id.is_trazet_user and
                        not order.subscription_id):  # Only for new subscriptions, not upsells

                    # Check if this is a paid subscription (not free plan)
                    has_paid_products = any(
                        line.product_id.recurring_invoice and not line.product_id.product_tmpl_id.is_free_plan
                        for line in order.order_line
                    )

                    if has_paid_products:
                        subscriptions_to_check.append(order.partner_id)

        # Call the original action_confirm first
        result = super().action_confirm()

        # After confirmation, close free plan subscriptions for customers who got paid subscriptions
        # (Only if we're not skipping closure logic)
        if not skip_closure:
            for partner in set(subscriptions_to_check):  # Remove duplicates
                self._close_free_plan_subscriptions_for_partner(partner)

        # Filter for newly confirmed subscriptions to send to Trazet
        new_subscriptions = self.filtered(
            lambda o: o.is_subscription and
                      o.subscription_state == '3_progress' and
                      not o.subscription_id and
                      not getattr(o, 'is_quantity_decrease', False)
        )

        # OPTIMIZED: Schedule Trazet processing after transaction commits
        if new_subscriptions:
            for subscription in new_subscriptions:
                if subscription.partner_id.is_trazet_user:
                    # Use postcommit to call existing method -
                    self.env.cr.postcommit.add(
                        lambda sub_id=subscription.id: self._process_single_subscription_trazet_sync(sub_id)
                    )

        return result

    def _process_single_subscription_trazet_sync(self, subscription_id):
        """
        Process Trazet sync for a single subscription after commit
        """
        try:
            # Get subscription in fresh transaction
            subscription = self.env['sale.order'].browse(subscription_id)

            if not subscription.exists() or not subscription.partner_id.is_trazet_user:
                return

            # Skip FIOS subscriptions - they sync to FIOS, not Trazet.
            if subscription._is_fios_subscription():
                _logger.info("Skipping Trazet sync for FIOS subscription %s", subscription.name)
                return

            # Skip API calls for free plan subscriptions - Trazet user may not exist yet
            if subscription._is_free_plan_subscription():
                _logger.info(
                    f"Skipping Trazet API call for free plan subscription {subscription.name}. "
                    f"Free plan users may not exist in Trazet yet."
                )
                subscription.message_post(
                    body=_("Trazet API call skipped - Free plan subscription (user may not exist in Trazet yet)"),
                    message_type='comment'
                )
                return

            # Use EXISTING methods - no changes needed!
            product_limits = subscription._calculate_trazet_product_limits(subscription.partner_id)

            if product_limits:
                # Send subscription limits to Trazet using EXISTING method
                limits_success, limits_error_msg = subscription._send_trazet_subscription_update(
                    subscription.partner_id,
                    product_limits
                )

                if limits_success:
                    # Send effective date using EXISTING method
                    effective_date_success, effective_date_message = subscription._send_plan_based_effective_date_to_trazet()

                    if effective_date_success:
                        # Both operations successful
                        subscription.message_post(
                            body=_(
                                "New subscription confirmed and sent to Trazet:\n"
                                "Subscription limits: %s\n"
                                "Effective date: %s\n"
                            ) % (product_limits, effective_date_message),
                            message_type='comment'
                        )

                        _logger.info(
                            f"Successfully sent both limits and validity-based effective date to Trazet "
                            f"for subscription {subscription.name}: {effective_date_message}"
                        )
                    else:
                        # Limits sent successfully but effective date failed
                        subscription.message_post(
                            body=_(
                                "New subscription limits sent to Trazet: %s\n"
                                "Warning: Failed to send effective date: %s"
                            ) % (product_limits, effective_date_message),
                            message_type='comment'
                        )

                        _logger.warning(
                            f"Sent limits but failed to send effective date for subscription "
                            f"{subscription.name}: {effective_date_message}"
                        )

                else:
                    _logger.error(f"Failed to send subscription limits to Trazet: {limits_error_msg}")
                    subscription.message_post(
                        body=_("Failed to send subscription limits to Trazet: %s") % limits_error_msg,
                        message_type='comment'
                    )

        except Exception as e:
            _logger.error(
                f"Error in async Trazet processing for subscription {subscription_id}: {e}",
                exc_info=True
            )

    def _calculate_projected_trazet_limits_after_decrease(self, decrease_lines):
        """
        Calculate what the TOTAL Trazet limits would be if the decrease was applied
        (across ALL active subscriptions for the partner)

        This method now REUSES _calculate_trazet_product_limits to avoid code duplication.

        :param decrease_lines: Dict with line_id as key and new_qty as value
        :return: Dictionary with projected total Trazet product limits
        """
        self.ensure_one()

        # Strategy: Temporarily modify line quantities, calculate, then restore

        # Step 1: Store original quantities and prepare changes
        original_quantities = {}
        all_affected_lines = {}

        # Collect main lines and their linked items
        for line_id_str, new_qty in decrease_lines.items():
            try:
                line_id = int(line_id_str)
                line = self.env['sale.order.line'].browse(line_id)

                if not line.exists() or line.order_id != self:
                    continue

                # Store original quantity
                original_quantities[line_id] = line.product_uom_qty
                all_affected_lines[line_id] = {
                    'line': line,
                    'new_qty': new_qty
                }

                # If this is a combo product, find all its linked items
                if line.product_id.type == 'combo':
                    combo_items = self.order_line.filtered(
                        lambda l: l.linked_line_id and l.linked_line_id.id == line_id
                    )

                    for item in combo_items:
                        # Store original quantity
                        original_quantities[item.id] = item.product_uom_qty

                        # Calculate new quantity for linked item
                        if line.product_uom_qty > 0:
                            ratio = item.product_uom_qty / line.product_uom_qty
                            item_new_qty = new_qty * ratio
                        else:
                            item_new_qty = 0

                        all_affected_lines[item.id] = {
                            'line': item,
                            'old_qty': item.product_uom_qty,
                            'new_qty': item_new_qty
                        }

            except (ValueError, TypeError) as e:
                _logger.error(f"Error processing line {line_id_str}: {e}")
                continue

        # Step 2: Temporarily modify the quantities IN MEMORY (without committing to DB)
        # Using write() with context to prevent triggers
        for line_id, line_info in all_affected_lines.items():
            line = line_info['line']
            new_qty = line_info['new_qty']

            # Temporarily set the new quantity in memory
            # This doesn't commit to database, just changes the Python object
            line.product_uom_qty = new_qty

            _logger.info(
                f"Temporarily projecting {line.product_id.name}: "
                f"{original_quantities[line_id]} → {new_qty} for calculation"
            )

        try:
            # Step 3: Calculate limits using the SAME method with temporary quantities
            # This reuses ALL the business logic including:
            # - allowExternalAPI → true/false
            # - collectPeriod → 365/90
            # - users → +1 logic
            # - Everything else!
            projected_limits = self._calculate_trazet_product_limits(self.partner_id)

            _logger.info(f"Projected limits after decrease: {projected_limits}")

            return projected_limits

        finally:
            # Step 4: ALWAYS restore original quantities (even if error occurs)
            for line_id, original_qty in original_quantities.items():
                line = self.env['sale.order.line'].browse(line_id)
                if line.exists():
                    line.product_uom_qty = original_qty
                    _logger.debug(f"Restored {line.product_id.name} quantity to {original_qty}")

    @api.onchange('grace_period_days')
    def _onchange_grace_period_days(self):
        """Show notification when grace period is changed"""
        if self.grace_period_days and self.is_subscription:
            return {
                # Explicitly echo the field back so the onchange response confirms the
                # selected value instead of leaving it to snapshot-diffing.
                'value': {'grace_period_days': self.grace_period_days},
                'warning': {
                    'title': _('Grace Period Selected'),
                    'message': _(
                        'You have selected a %s grace period. '
                        'Click the "Send to Trazet" button to apply this setting.'
                    ) % dict(self._fields['grace_period_days'].selection)[self.grace_period_days],
                    # Use a non-blocking toast instead of a modal dialog: opening a modal
                    # `Dialog` here was coinciding with the selected value being reverted.
                    'type': 'notification',
                }
            }

    @api.model
    def _cron_subscription_expiration(self):
        """
        Override to set context for automatic subscription closures
        This allows us to handle Trazet API errors differently for cron vs manual closes
        """
        # Set the context and call the original method
        return super(SaleOrder, self.with_context(cron_close=True))._cron_subscription_expiration()

    def set_close(self, close_reason_id=None, renew=False):
        """
        Override to update Trazet quantities when subscription is closed
        """
        # Check if this is being called from a cron job or manually
        is_cron_context = self.env.context.get('cron_close', False)

        # First, validate with Trazet API before actually closing subscriptions
        failed_subscriptions = []

        for order in self:
            if (order.is_subscription and
                    order.subscription_state in ['3_progress', '4_paused'] and
                    order.partner_id.is_trazet_user and
                    not order._is_fios_subscription()):

                try:
                    # Check if there are any other active subscriptions for this partner
                    other_active_subscriptions = self.env['sale.order'].search([
                        ('partner_id', '=', order.partner_id.id),
                        ('is_subscription', '=', True),
                        ('subscription_state', 'in', ['3_progress', '4_paused']),
                        ('state', '=', 'sale'),
                        ('id', '!=', order.id)  # Exclude the current subscription being closed
                    ])

                    # Calculate what the limits would be after closing this subscription
                    projected_limits = order._calculate_projected_trazet_limits_after_close()

                    # Check with Trazet API before proceeding
                    success, error_msg = order._send_trazet_subscription_update(
                        partner=order.partner_id,
                        product_limits=projected_limits
                    )

                    if not success:
                        if is_cron_context:
                            # For cron jobs: log error, create activity, but don't break the process
                            order._handle_trazet_close_failure(error_msg)
                            failed_subscriptions.append(order)
                        else:
                            # For manual closes: show error to user and prevent close
                            raise UserError(_("Cannot close subscription: %s") % error_msg)

                    # Handle deactivation datetime based on remaining subscriptions
                    if other_active_subscriptions:
                        # If other subscriptions exist, calculate earliest effective date
                        try:
                            # Calculate effective date for each remaining subscription (next_invoice_date + grace_period)
                            effective_dates = []

                            for subscription in other_active_subscriptions:
                                if not subscription.next_invoice_date:
                                    continue

                                # Calculate effective date considering individual grace periods
                                if subscription.grace_period_days:
                                    grace_days = int(subscription.grace_period_days)
                                    effective_date = subscription.next_invoice_date + timedelta(days=grace_days)
                                    date_type = f"next_invoice_date + {grace_days} days grace period"
                                else:
                                    effective_date = subscription.next_invoice_date
                                    date_type = "next_invoice_date (no grace period)"

                                effective_dates.append({
                                    'date': effective_date,
                                    'subscription': subscription,
                                    'base_date': subscription.next_invoice_date,
                                    'date_type': date_type,
                                    'grace_days': grace_days if subscription.grace_period_days else 0
                                })

                            if effective_dates and order.partner_id.user_ids:
                                # Find the earliest effective date
                                earliest = min(effective_dates, key=lambda x: x['date'])
                                deactivation_date = earliest['date']
                                source_subscription = earliest['subscription']
                                date_explanation = earliest['date_type']

                                trazet_user_id = order.partner_id.user_ids[0].id

                                # Convert to ISO8601 format for Trazet API (end of day)
                                deactivation_iso = deactivation_date.strftime('%Y-%m-%dT23:59:59.000Z')

                                # Send deactivation datetime to Trazet
                                deactivation_success = order._send_deactivation_to_trazet(
                                    trazet_user_id,
                                    deactivation_iso
                                )

                                if deactivation_success:
                                    # Build detailed log message
                                    log_message = _(
                                        "Deactivation datetime sent to Trazet: %s (%s)\n"
                                        "Source subscription: %s\n"
                                        "Base next invoice date: %s\n"
                                        "Grace period: %s days\n"
                                    ) % (
                                                      deactivation_date.strftime('%Y-%m-%d'),
                                                      date_explanation,
                                                      source_subscription.name,
                                                      earliest['base_date'].strftime('%Y-%m-%d'),
                                                      earliest['grace_days']
                                                  )


                                    order.message_post(body=log_message)

                                    _logger.info(
                                        f"Sent deactivation datetime to Trazet for partner {order.partner_id.name}: "
                                        f"{deactivation_date} ({date_explanation}). "
                                        f"Based on {len(other_active_subscriptions)} remaining subscriptions."
                                    )
                                else:
                                    _logger.warning(
                                        f"Failed to send deactivation datetime to Trazet for partner "
                                        f"{order.partner_id.name}"
                                    )
                            else:
                                _logger.warning(
                                    f"Cannot send deactivation datetime for partner {order.partner_id.name}: "
                                    f"No valid effective dates found or missing user account"
                                )

                        except Exception as e:
                            _logger.error(
                                f"Error calculating/sending earliest deactivation datetime to Trazet for partner "
                                f"{order.partner_id.name}: {str(e)}"
                            )
                            if not is_cron_context:
                                # For manual closes, this is not critical enough to prevent closure
                                # Just log the error and continue
                                pass

                    else:
                        # If no other active subscriptions remain, send immediate deactivation
                        try:
                            deactivation_datetime = datetime.now()

                            if order.partner_id.user_ids:
                                trazet_user_id = order.partner_id.user_ids[0].id

                                # Convert to ISO8601 format for Trazet API
                                deactivation_iso = deactivation_datetime.strftime('%Y-%m-%dT%H:%M:%S.000Z')

                                # Send deactivation datetime to Trazet
                                deactivation_success = order._send_deactivation_to_trazet(
                                    trazet_user_id,
                                    deactivation_iso
                                )

                                if deactivation_success:
                                    order.message_post(
                                        body=_(
                                            "Immediate deactivation datetime sent to Trazet: %s\n"
                                            "No other active subscriptions found for customer - deactivating now."
                                        ) % deactivation_datetime.strftime('%Y-%m-%d %H:%M:%S')
                                    )

                                    _logger.info(
                                        f"Sent immediate deactivation datetime to Trazet for partner {order.partner_id.name}: "
                                        f"{deactivation_datetime}"
                                    )
                                else:
                                    _logger.warning(
                                        f"Failed to send deactivation datetime to Trazet for partner "
                                        f"{order.partner_id.name}"
                                    )
                            else:
                                _logger.warning(
                                    f"Cannot send deactivation datetime for partner {order.partner_id.name}: "
                                    f"Missing user account"
                                )

                        except Exception as e:
                            _logger.error(
                                f"Error sending deactivation datetime to Trazet for partner "
                                f"{order.partner_id.name}: {str(e)}"
                            )
                            if not is_cron_context:
                                # For manual closes, this is not critical enough to prevent closure
                                # Just log the error and continue
                                pass

                except Exception as e:
                    if is_cron_context:
                        # For cron jobs: log unexpected errors but continue
                        order._handle_trazet_close_failure(str(e))
                        failed_subscriptions.append(order)
                    else:
                        # For manual closes: re-raise the exception
                        raise

        # Remove failed subscriptions from the recordset for cron jobs
        if is_cron_context and failed_subscriptions:
            subscriptions_to_close = self - self.env['sale.order'].union(*failed_subscriptions)
        else:
            subscriptions_to_close = self

        # If all Trazet validations pass, proceed with the original set_close method
        if subscriptions_to_close:
            result = super(SaleOrder, subscriptions_to_close).set_close(close_reason_id=close_reason_id, renew=renew)
        else:
            result = True

        return result

    def _handle_trazet_close_failure(self, error_msg):
        """
        Handle Trazet API failures for subscription close attempts
        Used for cron jobs to log errors without breaking the process
        """
        self.ensure_one()

        # Log the error
        _logger.error(
            f"Failed to close subscription {self.name} for partner {self.partner_id.name} "
            f"due to Trazet API error: {error_msg}"
        )

        # Create an activity for system users to review
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            summary=_("Subscription Close Failed - Trazet API Error"),
            note=_(
                "Automatic subscription closure failed due to Trazet API error.\n\n"
                "Subscription: %s\n"
                "Customer: %s\n"
                "Error: %s\n\n"
                "Please review and manually close if appropriate."
            ) % (self.name, self.partner_id.name, error_msg),
            user_id=self.user_id.id or self.env.ref('base.user_admin').id
        )

        # Add a message to the subscription
        self.message_post(
            body=_(
                "Automatic closure failed due to Trazet API error: %s\n"
                "An activity has been created for manual review."
            ) % error_msg,
            message_type='comment'
        )

        # Send notification to subscription managers
        subscription_managers = self.env['res.users'].search([
            ('group_ids', 'in', [self.env.ref('sales_team.group_sale_manager').id])
        ])

        if subscription_managers:
            self.message_notify(
                partner_ids=subscription_managers.mapped('partner_id').ids,
                body=_(
                    "Subscription closure blocked by Trazet API for customer %s.\n"
                    "Error: %s\n"
                    "Please review subscription: %s"
                ) % (self.partner_id.name, error_msg, self.name),
                subject=_("Subscription Close Failed - %s") % self.name
            )

    def _calculate_projected_trazet_limits_after_close(self):
        """
        Calculate what the TOTAL Trazet limits would be after closing this subscription
        (based on remaining active subscriptions for the partner)
        :return: Dictionary with projected total Trazet product limits
        """
        self.ensure_one()

        # Get other active subscriptions for this partner (excluding the one being closed)
        other_active_subscriptions = self.env['sale.order'].search([
            ('partner_id', '=', self.partner_id.id),
            ('is_subscription', '=', True),
            ('subscription_state', 'in', ['3_progress', '4_paused']),
            ('state', '=', 'sale'),
            ('id', '!=', self.id)  # Exclude the current subscription being closed
        ])

        # Calculate base quantities from remaining subscriptions
        base_limits = {}

        for subscription in other_active_subscriptions:
            subscription_lines = subscription.order_line.filtered(
                lambda l: l.recurring_invoice and l.product_id.trazet_product_key)

            for line in subscription_lines:
                trazet_key = line.product_id.trazet_product_key
                if trazet_key:
                    total_qty = line.product_uom_qty

                    if trazet_key in base_limits:
                        base_limits[trazet_key] += int(total_qty)
                    else:
                        base_limits[trazet_key] = int(total_qty)

        # Apply Trazet-specific business logic after calculating base quantities
        final_projected_limits = {}

        # Handle the case where we have some base limits
        for trazet_key, quantity in base_limits.items():
            if trazet_key == 'users':
                # Special handling: Trazet should always have 1 more user than Odoo
                final_projected_limits['user'] = quantity + 1
                _logger.info(f"Projected after close: {quantity} Odoo users remaining → {quantity + 1} Trazet users")

            elif trazet_key == 'allowExternalAPI':
                # Special handling: API Access is a boolean feature
                # CRITICAL: Check if quantity > 0!
                if quantity > 0:
                    final_projected_limits['allowExternalAPI'] = True
                    _logger.info(f"Projected after close: API Access remains enabled (quantity: {quantity})")
                else:
                    final_projected_limits['allowExternalAPI'] = False
                    _logger.info(f"Projected after close: API Access disabled (quantity is 0)")

            elif trazet_key == 'collectPeriod':
                # Special handling: 400 Days History
                # CRITICAL: Check if quantity > 0!
                if quantity > 0:
                    final_projected_limits['collectPeriod'] = 365
                    _logger.info(f"Projected after close: collectPeriod remains at 365 (quantity: {quantity})")
                else:
                    final_projected_limits['collectPeriod'] = 90
                    _logger.info(f"Projected after close: collectPeriod set to default 90 (quantity is 0)")

            else:
                # For all other product keys, use the calculated quantity as-is
                final_projected_limits[trazet_key] = quantity

        # If no other active subscriptions remain, set all product keys to defaults
        if not base_limits:
            final_projected_limits = {
                'user': 1,  # Even with 0 Odoo users, Trazet gets 1
                'geofences': 0,
                'notifications': 0,
                'devices': 0,
                'drivers': 0,
                'commands': 0,
                'collectPeriod': 0,  # Default when removed
                'allowExternalAPI': False,  # Default when removed
            }
            _logger.info(
                "No remaining subscriptions after close, sending defaults: user=1, collectPeriod=90, allowExternalAPI=false")
        else:
            # Ensure collectPeriod is always sent (default 90 if not in remaining subscriptions)
            if 'collectPeriod' not in final_projected_limits:
                final_projected_limits['collectPeriod'] = 90
                _logger.info(f"Projected after close: collectPeriod not in remaining subscriptions, sending default 90")

            # Ensure allowExternalAPI is always sent (default false if not in remaining subscriptions)
            if 'allowExternalAPI' not in final_projected_limits:
                final_projected_limits['allowExternalAPI'] = False
                _logger.info(f"Projected after close: allowExternalAPI not in remaining subscriptions, sending false")

        _logger.info(
            f"Projected limits after subscription close: Original: {base_limits}, Final: {final_projected_limits}")

        return final_projected_limits

    def _close_free_plan_subscriptions_for_partner(self, partner):
        """
        Close all active free plan subscriptions for a partner when they get a paid subscription
        No Trazet update needed here as action_confirm will handle the final quantities
        """
        try:
            # Find all active free plan subscriptions for this partner
            free_plan_subscriptions = self.env['sale.order'].search([
                ('partner_id', '=', partner.id),
                ('is_subscription', '=', True),
                ('subscription_state', 'in', ['3_progress', '4_paused']),
                ('state', '=', 'sale')
            ]).filtered(
                lambda sub: any(
                    line.product_id.recurring_invoice and line.product_id.product_tmpl_id.is_free_plan
                    for line in sub.order_line
                )
            )

            if free_plan_subscriptions:
                # Get the close reason for subscription upgrade
                upgrade_close_reason = self.env['sale.order.close.reason'].search([], limit=1)

                for free_subscription in free_plan_subscriptions:
                    try:
                        # Add message explaining why it's being closed
                        free_subscription.message_post(
                            body=_(
                                "Free plan subscription automatically closed because customer "
                                "purchased a paid subscription plan. Upgraded to paid service."
                            ),
                            message_type='comment'
                        )

                        # Close the free subscription directly without Trazet validation
                        # Use super() to bypass our Trazet validation in set_close
                        super(SaleOrder, free_subscription).set_close(
                            close_reason_id=upgrade_close_reason.id if upgrade_close_reason else None
                        )

                        _logger.info(
                            f"Automatically closed free plan subscription {free_subscription.name} "
                            f"for partner {partner.name} due to paid subscription purchase"
                        )

                    except Exception as e:
                        _logger.error(
                            f"Failed to close free plan subscription {free_subscription.name} "
                            f"for partner {partner.name}: {str(e)}"
                        )
                        # Continue with other subscriptions even if one fails
                        continue

        except Exception as e:
            _logger.error(
                f"Error while closing free plan subscriptions for partner {partner.name}: {str(e)}"
            )

    def _send_deactivation_to_trazet(self, trazet_user_id, deactivation_iso):
        """Send deactivation request to Trazet API"""
        user = self.env['res.users'].browse(trazet_user_id) if trazet_user_id else None
        trazet_api_url, trazet_auth_token = self._get_trazet_api_config(user)

        if not trazet_api_url or not trazet_auth_token:
            raise UserError(_(
                "Trazet API URL or Auth Token not configured in system parameters. "
                "Cannot send deactivation request."
            ))

        url = f"{trazet_api_url}/api/v2/odoo/{trazet_user_id}/deactivate"
        headers = {
            'Content-Type': 'application/json',
            'Trazet-Auth': trazet_auth_token
        }
        payload = {
            'deactivatedAt': deactivation_iso
        }

        partner = None
        try:
            user = self.env['res.users'].browse(trazet_user_id)
            if user.exists():
                partner = user.partner_id
        except:
            pass

        try:
            _logger.info(
                f"Sending deactivation request to Trazet for user {trazet_user_id}. "
                f"Deactivation date: {deactivation_iso}"
            )

            response = requests.patch(url, headers=headers, data=json.dumps(payload), timeout=30)
            response.raise_for_status()

            _logger.info(
                f"Successfully sent deactivation request to Trazet for user {trazet_user_id}. "
                f"Response: {response.status_code}"
            )

            # Log successful API call
            try:
                response_text = response.text
            except:
                response_text = 'Success (no response body)'

            self.env['api.retry.log'].create_success_log(
                api_endpoint='deactivation',
                url=url,
                headers=headers,
                payload=payload,
                partner=partner,
                sale_order=self,
                response_status=response.status_code,
                response_data=response_text,
                message=f"Successfully sent deactivation for user {trazet_user_id} at {deactivation_iso}"
            )

            return True

        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to send deactivation request to Trazet for user {trazet_user_id}: {e}"
            _logger.error(error_msg)

            self._create_retry_log('deactivation', url, headers, payload, partner, str(e))

            if hasattr(e, 'response') and e.response is not None:
                if 400 <= e.response.status_code < 500:
                    raise UserError(_(
                        "Trazet API returned an error: %s. Please check the request data."
                    ) % e.response.text)
                else:
                    raise UserError(_(
                        "Failed to communicate with Trazet API. Please try again later."
                    ))
            else:
                raise UserError(_(
                    "Failed to connect to Trazet API. Please check your internet connection."
                ))

    def _get_partner_closest_effective_date(self, partner):
        """
        Get the closest (earliest) effective date for a partner's active subscriptions
        This considers grace periods: next_invoice_date + grace_period_days for subscriptions with grace period
        EXCLUDES free plan subscriptions from consideration
        :param partner: res.partner record
        :return: tuple (datetime.date or False, subscription_record or False, str explanation)
        """
        active_subscriptions = self.env['sale.order'].search([
            ('partner_id', '=', partner.id),
            ('is_subscription', '=', True),
            ('subscription_state', 'in', ['3_progress', '4_paused']),
            ('next_invoice_date', '!=', False),
            ('state', '=', 'sale')
        ])

        if not active_subscriptions:
            return False, False, "No active subscriptions found"

        # Filter out free plan subscriptions and FIOS subscriptions (FIOS syncs to
        # FIOS, not Trazet).
        paid_subscriptions = active_subscriptions.filtered(
            lambda sub: not sub._is_fios_subscription() and not any(
                line.product_id.recurring_invoice and line.product_id.product_tmpl_id.is_free_plan
                for line in sub.order_line
            )
        )

        if not paid_subscriptions:
            return False, False, "No active paid (non-FIOS) subscriptions found"

        effective_dates = []

        for subscription in paid_subscriptions:
            # Check if subscription has grace period
            if subscription.grace_period_days:
                grace_days = int(subscription.grace_period_days)
                effective_date = subscription.next_invoice_date + timedelta(days=grace_days)
                date_type = f"next_invoice_date + {grace_days} days grace period"
            else:
                effective_date = subscription.next_invoice_date
                date_type = "next_invoice_date (no grace period)"

            effective_dates.append({
                'date': effective_date,
                'subscription': subscription,
                'base_date': subscription.next_invoice_date,
                'date_type': date_type,
                'grace_days': grace_days if subscription.grace_period_days else 0
            })

        if not effective_dates:
            return False, False, "No valid dates found from paid subscriptions"

        # Find the earliest effective date
        earliest = min(effective_dates, key=lambda x: x['date'])

        return earliest['date'], earliest['subscription'], earliest['date_type']

    def update_partner_trazet_effective_date(self, partner):
        """
        Update Trazet with the closest effective date for a partner
        Considers grace periods: sends next_invoice_date + grace_period_days for subscriptions with grace
        :param partner: res.partner record
        :return: tuple (success: bool, message: str)
        """
        if not partner.is_trazet_user:
            return False, "Partner is not a Trazet user"

        if not partner.user_ids:
            return False, "Partner doesn't have an associated user account"

        trazet_user_id = partner.user_ids[0].id
        closest_date, source_subscription, date_explanation = self._get_partner_closest_effective_date(partner)

        if not closest_date:
            _logger.info(f"No active subscriptions with effective dates found for partner {partner.name}")
            return True, "No active subscriptions found"

        # Convert to ISO8601 format for Trazet API
        effective_date_iso = closest_date.strftime('%Y-%m-%dT23:59:59.000Z')

        # Send to Trazet (using the deactivation endpoint since that's what handles grace periods)
        success = self._send_deactivation_to_trazet(trazet_user_id, effective_date_iso)

        if success:
            _logger.info(
                f"Successfully updated Trazet effective date for partner {partner.name}. "
                f"Date: {closest_date}, Source: {source_subscription.name}, Type: {date_explanation}"
            )
            return True, f"Effective date updated: {closest_date} ({date_explanation})"
        else:
            return False, "Failed to send to Trazet API"

    @api.model
    def cron_update_trazet_effective_dates(self):
        """
        Cron job to update Trazet with effective dates for all active subscriptions
        For partners with multiple subscriptions, sends the closest (earliest) effective date
        Considers grace periods: next_invoice_date + grace_period_days
        """
        _logger.info("Starting Trazet effective date update cron job")

        # Get all partners with active subscriptions that are Trazet users
        partners_with_subscriptions = self.env['res.partner'].search([
            ('is_trazet_user', '=', True)
        ])

        # Filter to only partners that actually have active subscriptions
        partners_to_update = []
        for partner in partners_with_subscriptions:
            active_subs = self.env['sale.order'].search_count([
                ('partner_id', '=', partner.id),
                ('is_subscription', '=', True),
                ('subscription_state', 'in', ['3_progress', '4_paused']),
                ('next_invoice_date', '!=', False),
                ('state', '=', 'sale')
            ])
            if active_subs > 0:
                partners_to_update.append(partner)

        success_count = 0
        error_count = 0

        for partner in partners_to_update:
            try:
                success, message = self.update_partner_trazet_effective_date(partner)

                if success:
                    success_count += 1
                else:
                    error_count += 1
                    _logger.error(f"Failed to update Trazet for partner {partner.name}: {message}")

            except Exception as e:
                error_count += 1
                _logger.error(f"Unexpected error for partner {partner.name}: {str(e)}")

        # Log summary
        _logger.info(
            f"Trazet effective date update completed. "
            f"Success: {success_count}, Errors: {error_count}, Total: {len(partners_to_update)}"
        )

        return {
            'success_count': success_count,
            'error_count': error_count,
            'total_processed': len(partners_to_update)
        }

    def action_send_effective_date_to_trazet(self):
        """
        Manual action to send effective date to Trazet for the current subscription's partner
        Considers grace periods: next_invoice_date + grace_period_days
        """
        self.ensure_one()

        if not self.is_subscription:
            raise UserError(_("This action can only be performed on subscriptions."))

        if not self.partner_id.is_trazet_user:
            raise UserError(_("Customer is not a Trazet user."))

        if not self.partner_id.user_ids:
            raise UserError(_("Customer doesn't have an associated user account."))

        # Skip for free plan subscriptions
        if self._is_free_plan_subscription():
            raise UserError(_("Cannot send effective date for free plan subscriptions. Free plan users may not exist in Trazet yet."))

        # Update Trazet with the partner's closest effective date
        success, message = self.update_partner_trazet_effective_date(self.partner_id)

        if success:
            # Get the actual date that was sent
            closest_date, source_subscription, date_explanation = self._get_partner_closest_effective_date(
                self.partner_id)

            grace_days = int(source_subscription.grace_period_days or 0)
            base_date = source_subscription.next_invoice_date
            effective_date = base_date + timedelta(days=grace_days)

            log_message = _(
                "Effective date sent to Trazet successfully.\n"
                "Grace Period: %s days\n"
                "Source Subscription: %s\n"
                "Next Invoice Date: %s\n"
                "Effective Date (with Grace): %s\n"
            ) % (
                              grace_days,
                              source_subscription.name if source_subscription else "Unknown",
                              base_date.strftime('%Y-%m-%d'),
                              effective_date.strftime('%Y-%m-%d')
                          )

            all_partner_subs = self.env['sale.order'].search([
                ('partner_id', '=', self.partner_id.id),
                ('is_subscription', '=', True),
                ('subscription_state', 'in', ['3_progress', '4_paused']),
                ('next_invoice_date', '!=', False),
                ('state', '=', 'sale'),
                ('id', '!=', source_subscription.id)
            ])

            if all_partner_subs:
                log_message += _("\nOther Active Subscriptions:\n")
                for sub in all_partner_subs:
                    sub_grace_days = int(sub.grace_period_days or 0)
                    sub_base_date = sub.next_invoice_date
                    sub_effective_date = sub_base_date + timedelta(days=sub_grace_days)
                    log_message += f"  - {sub.name}: {sub_base_date.strftime('%Y-%m-%d')} + {sub_grace_days}d = {sub_effective_date.strftime('%Y-%m-%d')}\n"

                if effective_date == closest_date:
                    log_message += _("Used Current Subscription + Grace Period date\n")
                else:
                    earlier = all_partner_subs.filtered(
                        lambda s: (s.next_invoice_date + timedelta(days=int(s.grace_period_days or 0))) == closest_date)
                    if earlier:
                        log_message += _("Used Earlier Date from: %s\n") % earlier[0].name
                    else:
                        log_message += _("Used Earlier Date (source unknown)\n")
            else:
                log_message += _(
                    "\nNo other active subscriptions found.\nUsed Current Subscription + Grace Period date\n")

            log_message += _("Final Effective Date Sent: %s") % closest_date.strftime('%Y-%m-%d')

            self.message_post(body=log_message)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Effective date sent to Trazet successfully!'),
                    'type': 'success'
                }
            }
        else:
            raise UserError(_("Failed to send effective date to Trazet: %s") % message)


    def _send_plan_based_effective_date_to_trazet(self):
        """Send effective date based on plan billing period + grace period to Trazet"""
        self.ensure_one()

        if not self.partner_id.is_trazet_user or not self.partner_id.user_ids:
            return False, "Partner is not a Trazet user or missing user account"

        # Skip for free plan subscriptions
        if self._is_free_plan_subscription():
            return False, "Free plan subscription - user may not exist in Trazet yet"

        if not self.plan_id or not self.plan_id.billing_period:
            return False, "No subscription plan or billing period configured"

        try:
            # Calculate next billing date: start_date + billing_period
            start_date = self.start_date or fields.Date.today()
            next_billing_date = start_date + self.plan_id.billing_period

            # Apply grace period if configured
            grace_days = int(self.grace_period_days or 0)
            effective_date = next_billing_date + timedelta(days=grace_days)

            # Get closest date from other subscriptions (if any)
            closest_date, _, _ = self._get_partner_closest_effective_date(self.partner_id)

            # Pick earlier of the two dates
            final_date = min(effective_date, closest_date) if closest_date else effective_date
            effective_date_iso = final_date.strftime('%Y-%m-%dT23:59:00.000Z')

            trazet_user_id = self.partner_id.user_ids[0].id
            if effective_date_iso:
                success = self._send_deactivation_to_trazet(trazet_user_id, effective_date_iso)

                if success:
                    return True, f"{effective_date.strftime('%Y-%m-%d')} (start: {start_date} + {self.plan_id.billing_period} + {grace_days} grace days)"
                else:
                    return False, "Failed to send to Trazet API"

        except Exception as e:
            return False, f"Error sending plan-based effective date: {str(e)}"

    def _create_retry_log(self, api_endpoint, url, headers, payload, partner, error_msg):
        """
        Create a retry log entry for failed API calls using a separate cursor to ensure persistence

        Skip retry log creation for:
        - Free plan subscription limit updates (users may not exist in Trazet yet)

        Always create retry logs for:
        - Paid subscription failures
        - Deactivation endpoint failures
        """

        # Only skip retry logs for subscription_update endpoint on free plans
        if self and self.is_free_plan:
            _logger.info(
                f"Skipping retry log creation for free plan subscription {self.name}. "
                f"Partner: {partner.name if partner else 'Unknown'}. "
                f"Free plan users may not exist in Trazet yet."
            )
            return None

        # Use a new cursor to ensure the retry log persists even if main transaction fails
        with self.env.registry.cursor() as new_cr:
            new_env = api.Environment(new_cr, self.env.uid, self.env.context)
            now_utc = datetime.now(pytz.UTC)
            next_retry_time_utc = now_utc + timedelta(minutes=2)
            next_retry_time = next_retry_time_utc.replace(tzinfo=None)

            try:
                retry_log = new_env['api.retry.log'].sudo().create({
                    'api_endpoint': api_endpoint,
                    'url': url,
                    'headers': json.dumps(headers),
                    'payload': json.dumps(payload),
                    'partner_id': partner.id if partner else None,
                    'sale_order_id': self.id if self else None,
                    'state': 'pending',
                    'retry_count': 0,
                    'last_error': error_msg,
                    'next_retry_time': next_retry_time  # First retry in 2 minutes
                })

                # Commit the new cursor
                new_cr.commit()
                _logger.info(f"Created retry log {retry_log.id} for failed {api_endpoint} API call")
                return retry_log.id

            except Exception as e:
                _logger.error(f"Failed to create retry log for {api_endpoint}: {e}")
                new_cr.rollback()
                return None