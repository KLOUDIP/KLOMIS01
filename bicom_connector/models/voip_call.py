# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only.
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class VoipCall(models.Model):
    _inherit = "voip.call"

    log_id = fields.Char(string="Log ID")
    is_recording_uploaded = fields.Boolean(string='Is Recording Uploaded?')
    asteriskcallid_one = fields.Char(string="Asterisk Call ID 1")
    asteriskcallid_two = fields.Char(string="Asterisk Call ID 2")
    log_note = fields.Text(string="Log Note")
    duration = fields.Integer(string="Duration")
    state = fields.Selection(selection_add=[('answered', "Answered"), ('unanswered', "Unanswered")])

    def _cron_update_call_recording(self):
        # Stub: SSH recording pull removed. Kept so any surviving ir.cron
        # record is a no-op instead of an error.
        _logger.info("bicom_connector shell: _cron_update_call_recording is disabled.")
        return True

    def add_voice_clip_to_log_embedded(self, voice_clip_data):
        # Stub: kept for signature compatibility only.
        return False
