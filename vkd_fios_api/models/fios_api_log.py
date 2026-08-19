# -*- coding: utf-8 -*-
import json
import logging
from datetime import datetime, timedelta

import pytz

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Exponential backoff schedule (minutes) between retries.
BACKOFF_MINUTES = [2, 10, 30]


class FiosApiLog(models.Model):
    _name = 'fios.api.log'
    _description = 'FIOS API Call Log'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    display_name = fields.Char(compute='_compute_display_name', store=True)

    svc = fields.Char(string='FIOS Service', required=True, index=True,
                      help="e.g. core/create_user, account/create_account")
    params = fields.Text(string='Request Params', help='JSON params (secrets scrubbed)')
    response_data = fields.Text(string='Response Data')

    state = fields.Selection([
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ], default='pending', required=True, index=True)

    retry_count = fields.Integer(string='Retry Count', default=0)
    max_retries = fields.Integer(string='Max Retries', default=3)
    next_retry_time = fields.Datetime(string='Next Retry Time', index=True)

    partner_id = fields.Many2one('res.partner', string='Partner', index=True, ondelete='set null')
    error_code = fields.Integer(string='FIOS Error Code')
    last_error = fields.Text(string='Last Error')
    success_message = fields.Text(string='Success Message')

    @api.depends('svc', 'partner_id', 'state', 'create_date')
    def _compute_display_name(self):
        for record in self:
            partner_name = record.partner_id.name if record.partner_id else 'System'
            date_str = record.create_date.strftime('%Y-%m-%d %H:%M') if record.create_date else 'N/A'
            record.display_name = f"{record.svc} · {partner_name} ({record.state}) - {date_str}"

    @api.model
    def log_success(self, svc, params, partner=None, response_data=None, message=None):
        try:
            self.sudo().create({
                'svc': svc,
                'params': json.dumps(params, default=str),
                'partner_id': partner.id if partner else False,
                'state': 'success',
                'retry_count': 0,
                'response_data': json.dumps(response_data, default=str) if response_data else None,
                'success_message': message or _("Call succeeded at %s") % fields.Datetime.now(),
                'next_retry_time': False,
            })
        except Exception as e:
            _logger.error("FIOS: failed to write success log for %s: %s", svc, e)

    @api.model
    def log_failure(self, svc, params, partner=None, error_code=None, error_msg=None, retryable=True):
        try:
            vals = {
                'svc': svc,
                'params': json.dumps(params, default=str),
                'partner_id': partner.id if partner else False,
                'error_code': error_code,
                'last_error': error_msg,
                'retry_count': 0,
            }
            if retryable:
                now_utc = datetime.now(pytz.UTC).replace(tzinfo=None)
                vals['state'] = 'pending'
                vals['next_retry_time'] = now_utc + timedelta(minutes=BACKOFF_MINUTES[0])
            else:
                vals['state'] = 'failed'
                vals['next_retry_time'] = False
            return self.sudo().create(vals)
        except Exception as e:
            _logger.error("FIOS: failed to write failure log for %s: %s", svc, e)
            return self.browse()

    def action_retry_now(self):
        self.ensure_one()
        if self.state == 'success':
            raise UserError(_("This call already succeeded and cannot be retried."))
        success, error_msg = self._execute_retry()
        msg_type = 'success' if success else 'danger'
        title = _('Success') if success else _('Retry Failed')
        message = _('Retry succeeded!') if success else _('Retry failed: %s') % error_msg
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message, 'type': msg_type},
        }

    def _execute_retry(self):
        self.ensure_one()
        from .fios_api_client import FiosApiError
        try:
            params = json.loads(self.params) if self.params else {}
            result = self.env['fios.api.client'].call(self.svc, params)
            self.write({
                'state': 'success',
                'last_error': False,
                'response_data': json.dumps(result, default=str),
                'success_message': _("Retry succeeded at %s") % fields.Datetime.now(),
                'next_retry_time': False,
            })
            return True, None
        except FiosApiError as e:
            self._register_failure(e.message, error_code=e.code, retryable=e.is_retryable)
            return False, e.message
        except Exception as e:
            self._register_failure(str(e), retryable=True)
            return False, str(e)

    def _register_failure(self, error_msg, error_code=None, retryable=True):
        new_count = self.retry_count + 1
        now_utc = datetime.now(pytz.UTC).replace(tzinfo=None)
        if retryable and new_count < self.max_retries:
            delay = BACKOFF_MINUTES[min(new_count - 1, len(BACKOFF_MINUTES) - 1)]
            next_retry = now_utc + timedelta(minutes=delay)
            state = 'pending'
        else:
            next_retry = False
            state = 'failed'
        self.write({
            'state': state,
            'retry_count': new_count,
            'error_code': error_code,
            'last_error': error_msg,
            'next_retry_time': next_retry,
        })

    @api.model
    def cron_retry_failed_calls(self):
        now_utc = datetime.now(pytz.UTC).replace(tzinfo=None)
        domain = [
            ('state', '=', 'pending'),
            ('retry_count', '<', 3),
            '|', ('next_retry_time', '=', False), ('next_retry_time', '<=', now_utc),
        ]
        logs = self.search(domain, limit=20)
        success, errors = 0, 0
        for log in logs:
            try:
                ok, _err = log._execute_retry()
                success += 1 if ok else 0
                errors += 0 if ok else 1
            except Exception as e:
                errors += 1
                _logger.error("FIOS: unexpected error retrying log %s: %s", log.id, e, exc_info=True)
        _logger.info("FIOS retry cron done. success=%s errors=%s total=%s", success, errors, len(logs))
        return {'success': success, 'errors': errors, 'total': len(logs)}