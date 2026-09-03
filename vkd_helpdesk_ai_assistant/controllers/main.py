import json
from markupsafe import Markup, escape
from odoo import http
from odoo.http import request, Response


class IrisIntegrationController(http.Controller):

    def _authenticate(self):
        """Validates the x-api-key header against the System Parameter."""
        api_key = request.httprequest.headers.get('x-api-key')
        expected_key = request.env['ir.config_parameter'].sudo().get_param('iris.api_key')
        return api_key and expected_key and api_key == expected_key

    def _json_response(self, data, status=200):
        return Response(json.dumps(data), status=status, content_type='application/json')

    def _get_iris_partner(self):
        """Ensures an 'Iris Voice AI' contact exists for chatter attribution."""
        partner = request.env['res.partner'].sudo().search([('name', '=', 'Iris Voice AI')], limit=1)
        if not partner:
            partner = request.env['res.partner'].sudo().create({'name': 'Iris Voice AI'})
        return partner

    @http.route('/api/voice/ticket/create', type='http', auth='public', methods=['POST'], csrf=False)
    def create_ticket(self, **kwargs):
        """Use Case 1: Log a new query with flexible Phone or Email lookup."""
        if not self._authenticate():
            return self._json_response({'error': 'Unauthorized'}, 401)

        try:
            payload = json.loads(request.httprequest.data)
            caller_phone = payload.get('caller_phone')
            caller_email = payload.get('caller_email')

            domain = []
            if caller_phone:
                domain.append(('phone', 'ilike', caller_phone))
            if caller_email:
                domain.append(('email', '=ilike', caller_email.strip()))

            if len(domain) == 2:
                domain = ['|'] + domain

            partner = request.env['res.partner'].sudo().search(domain, limit=1) if domain else False
            partner_id = partner.id if partner else False

            # Fetch default Helpdesk team to keep UI visible
            team = request.env['helpdesk.team'].sudo().search([], limit=1)
            team_id = team.id if team else False

            ticket = request.env['helpdesk.ticket'].sudo().create({
                'name': payload.get('issue_title', 'Voice AI Support Query'),
                'description': payload.get('issue_description'),
                'partner_id': partner_id,
                'team_id': team_id
            })

            return self._json_response({
                'status': 'success',
                'ticket_reference': f"#{ticket.id}"
            })
        except Exception as e:
            return self._json_response({'error': str(e)}, 500)

    @http.route('/api/voice/ticket/status', type='http', auth='public', methods=['POST'], csrf=False)
    def check_status(self, **kwargs):
        """Use Case 2: Check ticket status using ticket_number."""
        if not self._authenticate():
            return self._json_response({'error': 'Unauthorized'}, 401)

        try:
            payload = json.loads(request.httprequest.data)
            ticket_id = payload.get('ticket_number')

            if not ticket_id:
                return self._json_response({'error': 'Missing ticket_number'}, 400)

            ticket = request.env['helpdesk.ticket'].sudo().browse(int(ticket_id))

            if not ticket.exists():
                return self._json_response({'error': 'Ticket not found'}, 444)

            stage_name = ticket.stage_id.name or 'New'

            # Security Rule: Hide finance/payment hold stages
            if 'Payment Hold' in stage_name or 'Finance' in stage_name:
                return self._json_response({
                    'status': 'success',
                    'spoken_status': 'Your ticket is currently with our billing department. Please speak with an agent for more details.'
                })

            stage_mapping = {
                'New': 'Your ticket has been logged and is awaiting review.',
                'In Progress': 'Our technical team is currently investigating your issue.',
                'Solved': 'Your ticket has been marked as resolved.',
                'Closed': 'Your ticket has been closed.'
            }

            friendly_status = stage_mapping.get(stage_name, f"Your ticket is currently in the {stage_name} stage.")

            return self._json_response({
                'status': 'success',
                'spoken_status': friendly_status
            })
        except Exception as e:
            return self._json_response({'error': str(e)}, 500)

    @http.route('/api/voice/ticket/comment', type='http', auth='public', methods=['POST'], csrf=False)
    def add_comment(self, **kwargs):
        """Use Case 3: Add a voice comment styled from Iris Voice AI."""
        if not self._authenticate():
            return self._json_response({'error': 'Unauthorized'}, 401)

        try:
            payload = json.loads(request.httprequest.data)
            ticket_id = payload.get('ticket_number')
            comment_text = payload.get('comment_text')

            if not ticket_id or not comment_text:
                return self._json_response({'error': 'Missing ticket_number or comment_text'}, 400)

            ticket = request.env['helpdesk.ticket'].sudo().browse(int(ticket_id))

            if not ticket.exists():
                return self._json_response({'error': 'Ticket not found'}, 404)

            iris_partner = self._get_iris_partner()

            # Wrap in Markup so Odoo renders rich HTML in Chatter while escaping raw user text safely
            formatted_body = Markup("<p><strong>Voice Call Note:</strong></p><p>%s</p>") % escape(comment_text)

            ticket.sudo().message_post(
                body=formatted_body,
                author_id=iris_partner.id,
                message_type='comment',
                subtype_xmlid='mail.mt_note'
            )

            return self._json_response({'status': 'success', 'message': f'Comment posted to ticket #{ticket.id}'})
        except Exception as e:
            return self._json_response({'error': str(e)}, 500)
