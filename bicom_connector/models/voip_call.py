# -*- coding: utf-8 -*-
import logging
import paramiko
import base64
from markupsafe import Markup

from odoo import fields, models

_logger = logging.getLogger(__name__)


class VoipCall(models.Model):
    _inherit = "voip.call"

    log_id = fields.Char(string="Log ID")
    is_recording_uploaded = fields.Boolean(string='Is Recording Uploaded?')
    asteriskcallid_one = fields.Char(string="Asterisk Call ID 1")
    asteriskcallid_two = fields.Char(string="Asterisk Call ID 2")
    log_note = fields.Text(string="Log Note")

    def _cron_update_call_recording(self):
        # Setting up the SSH client
        calls = self.search([('is_recording_uploaded', '=', False), ('asteriskcallid_one', '!=', False)])
        for rec in calls:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            url = 'comsl.kloudip.com'
            username = 'root'
            password = 'Klo_PND23_tiger'
            port = 2020

            try:
                # Connecting to the SFTP server
                client.connect(url, username=username, password=password, port=port)
                sftp = client.open_sftp()

                file_name = rec.asteriskcallid_one
                _logger.info('---------------------------------------')
                _logger.info(file_name)

                # Opening the file in binary mode
                with sftp.file(f'/opt/pbxware/pw/var/spool/asterisk/monitor/{file_name}.mp3', 'rb') as file:
                    binary_data = file.read()  # Reading the file as binary

                # base64_encoded_data is a bytes object, you might need it as a string
                voice_clip_data = base64.b64encode(binary_data).decode('utf-8')
                rec.add_voice_clip_to_log_embedded(voice_clip_data)

            except Exception as error:
                _logger.error('Error connecting to remote server! Error: %s', str(error))
            finally:
                # Closing the connection
                sftp.close()
                client.close()

    def add_voice_clip_to_log_embedded(self, voice_clip_data):
        # HTML content embedding the audio
        attachment = self.env['ir.attachment'].create({
            'name': 'Recording.mp3',
            'type': 'binary',
            'datas': voice_clip_data,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'audio/mpeg',  # Adjust mimetype according to your image format
        })

        # Create a log note with the attachment
        message = self.partner_id.message_post(
            body=Markup(self.log_note),
            message_type='comment',
            attachment_ids=[attachment.id]
        )
        self.write({'is_recording_uploaded': True})
        return message
