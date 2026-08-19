# -*- coding: utf-8 -*-
import json
import logging
from datetime import datetime, timedelta

import pytz
import requests

from odoo import models, fields, api, _
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class ApiRetryLog(models.Model):
    _name = 'api.retry.log'
    _description = 'Trazet API Call Log'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    display_name = fields.Char(compute='_compute_display_name', store=True)
    api_endpoint = fields.Selection([
        ('subscription_update', 'Subscription Update'),
        ('deactivation', 'Deactivation')
    ], required=True, index=True)

    url = fields.Text(string='Request URL', required=True)
    headers = fields.Text(string='Request Headers')
    payload = fields.Text(string='Request Payload')
    response_data = fields.Text(string='Response Data', help='API response for successful calls')
    response_status_code = fields.Integer(string='Response Status Code')

    state = fields.Selection([
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed')
    ], default='pending', required=True, index=True)

    retry_count = fields.Integer(string='Retry Count', default=0)
    max_retries = fields.Integer(string='Max Retries', default=3)
    next_retry_time = fields.Datetime(string='Next Retry Time', index=True)

    partner_id = fields.Many2one('res.partner', string='Partner', index=True)
    sale_order_id = fields.Many2one('sale.order', string='Sale Order', index=True)

    last_error = fields.Text(string='Last Error')
    success_message = fields.Text(string='Success Message', help='Details for successful API calls')

    @api.depends('api_endpoint', 'partner_id', 'state', 'create_date')
    def _compute_display_name(self):
        for record in self:
            partner_name = record.partner_id.name if record.partner_id else 'Unknown'
            date_str = record.create_date.strftime('%Y-%m-%d %H:%M') if record.create_date else 'N/A'
            record.display_name = f"{partner_name} ({record.state}) - {date_str}"

    def action_retry_now(self):
        self.ensure_one()
        if self.state == 'success':
            raise UserError(_("This API call has already succeeded and cannot be retried."))

        success, error_msg = self._execute_retry()

        if success:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('API retry successful!'),
                    'type': 'success'
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Retry Failed'),
                    'message': _('Retry failed: %s') % error_msg,
                    'type': 'danger'
                }
            }

    def _execute_retry(self):
        self.ensure_one()

        try:
            payload_data = json.loads(self.payload) if self.payload else {}

            if self.sale_order_id:
                sale_order = self.sale_order_id
            else:
                sale_order = self.env['sale.order'].sudo()

            # Get user from partner to determine correct token
            user = None
            if self.partner_id and self.partner_id.user_ids:
                user = self.partner_id.user_ids[0]

            trazet_api_url, trazet_auth_token = sale_order._get_trazet_api_config(user)

            if not trazet_api_url or not trazet_auth_token:
                error_msg = "API configuration missing"
                self._update_retry_failure(error_msg)
                return False, error_msg

            headers = {
                'Content-Type': 'application/json',
                'Trazet-Auth': trazet_auth_token
            }

            response = requests.patch(
                self.url,
                headers=headers,
                data=json.dumps(payload_data),
                timeout=30
            )

            if response.status_code == 200:
                try:
                    response_text = response.text
                except:
                    response_text = 'Success (no response body)'

                self.write({
                    'state': 'success',
                    'last_error': None,
                    'response_status_code': response.status_code,
                    'response_data': response_text,
                    'success_message': f'API call successful at {fields.Datetime.now()}'
                })
                return True, None
            else:
                try:
                    error_data = response.json()
                    error_message = error_data.get('message', 'Unknown error')
                except:
                    error_message = f"HTTP {response.status_code}: {response.text}"

                self._update_retry_failure(error_message)
                return False, error_message

        except requests.exceptions.Timeout:
            error_msg = "Connection timeout. Please try again."
            self._update_retry_failure(error_msg)
            return False, error_msg

        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to connect to API service: {str(e)}"
            self._update_retry_failure(error_msg)
            return False, error_msg

    def _update_retry_failure(self, error_msg):
        new_retry_count = self.retry_count + 1
        now_utc = datetime.now(pytz.UTC)
        # Calculate next retry time with exponential backoff
        if new_retry_count < self.max_retries:
            # Exponential backoff: 2min, 10min, 30min
            backoff_minutes = [2, 10, 30]
            delay_minutes = backoff_minutes[min(new_retry_count - 1, len(backoff_minutes) - 1)]
            next_retry_time_utc = now_utc  + timedelta(minutes=delay_minutes)
            next_retry_time = next_retry_time_utc.replace(tzinfo=None)
            state = 'pending'
        else:
            next_retry_time = None
            state = 'failed'

        self.write({
            'state': state,
            'retry_count': new_retry_count,
            'last_error': error_msg,
            'next_retry_time': next_retry_time
        })

    @api.model
    def create_success_log(self, api_endpoint, url, headers, payload, partner, sale_order, response_status, response_data, message=None):
        try:
            self.sudo().create({
                'api_endpoint': api_endpoint,
                'url': url,
                'headers': json.dumps(headers),
                'payload': json.dumps(payload),
                'partner_id': partner.id if partner else None,
                'sale_order_id': sale_order.id if sale_order else None,
                'state': 'success',
                'retry_count': 0,
                'response_status_code': response_status,
                'response_data': response_data,
                'success_message': message or f'API call successful at {fields.Datetime.now()}',
                'last_error': None,
                'next_retry_time': None
            })
            _logger.info(f"Created success log for {api_endpoint} API call")
        except Exception as e:
            _logger.error(f"Failed to create success log for {api_endpoint}: {e}")

    @api.model
    def cron_retry_failed_api_calls(self):
        _logger.info("Starting API retry cron job")
        now_utc = datetime.now(pytz.UTC).replace(tzinfo=None)

        # Find records ready for retry
        domain = [
            ('state', '=', 'pending'),
            ('retry_count', '<', 3),
            '|',
            ('next_retry_time', '=', False),
            ('next_retry_time', '<=', now_utc)
        ]

        retry_logs = self.search(domain, limit=20)  # Limit to avoid overload

        success_count = 0
        error_count = 0

        for log in retry_logs:
            try:
                success, error_msg = log._execute_retry()
                if success:
                    success_count += 1
                    _logger.info(f"Successfully retried API call {log.id} ({log.api_endpoint})")
                else:
                    error_count += 1
                    _logger.warning(f"Retry failed for API call {log.id}: {error_msg}")

            except Exception as e:
                error_count += 1
                _logger.error(f"Unexpected error retrying API call {log.id}: {str(e)}", exc_info=True)

        _logger.info(f"API retry cron completed. Success: {success_count}, Errors: {error_count}")

        return {
            'success_count': success_count,
            'error_count': error_count,
            'total_processed': len(retry_logs)
        }
