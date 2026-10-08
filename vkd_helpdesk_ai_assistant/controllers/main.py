import json
from markupsafe import Markup, escape
from odoo import SUPERUSER_ID, http
from odoo.exceptions import UserError
from odoo.http import request, Response
from odoo.tools import html2plaintext


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
        """Use Case 1: Log a new query with Parent Contact Routing and Exact Phone Match."""
        if not self._authenticate():
            return self._json_response({'error': 'Unauthorized'}, 401)

        try:
            payload = json.loads(request.httprequest.data)
            customer_id = payload.get('customer_id') or payload.get('partner_id')
            caller_phone = payload.get('caller_phone')
            caller_email = payload.get('caller_email')

            partner = False

            # 1. Direct Lookup by Odoo Customer ID
            if customer_id:
                try:
                    p = request.env['res.partner'].sudo().browse(int(customer_id))
                    if p.exists():
                        partner = p
                except (ValueError, TypeError):
                    pass

            # 2. Fallback to Exact Phone or Email lookup
            if not partner:
                domain = []
                if caller_phone:
                    domain.append(('phone', '=', caller_phone))
                if caller_email:
                    domain.append(('email', '=ilike', caller_email.strip()))

                if len(domain) == 2:
                    domain = ['|'] + domain

                if domain:
                    partner = request.env['res.partner'].sudo().search(domain, limit=1)

            # Route ticket to Parent Contact if it exists, otherwise use the matched contact
            ticket_partner_id = partner.parent_id.id if (partner and partner.parent_id) else (
                partner.id if partner else False)

            target_company = request.env['res.company'].sudo().search([
                ('name', '=ilike', 'KLOUDIP (Pvt) Ltd')
            ], limit=1)

            team_domain = [('name', '=', 'Support')]
            if target_company:
                team_domain.append(('company_id', '=', target_company.id))

            team = request.env['helpdesk.team'].sudo().search(team_domain, limit=1)

            if not team:
                team = request.env['helpdesk.team'].sudo().search([('name', '=', 'Support')], limit=1)

            ticket_vals = {
                'name': payload.get('issue_title', 'Voice AI Support Query'),
                'description': payload.get('issue_description'),
                'partner_id': ticket_partner_id,
                'team_id': team.id if team else False,
                'company_id': target_company.id if target_company else False,
            }

            ticket_env = request.env['helpdesk.ticket'].sudo().with_user(SUPERUSER_ID)
            if target_company:
                ticket_env = ticket_env.with_company(target_company)

            ticket = ticket_env.create(ticket_vals)

            response_data = {
                'status': 'success',
                'ticket_reference': f"#{ticket.id}"
            }

            if partner and partner.fios_provision_state == 'active':
                response_data['fios_days_left'] = partner.fios_days_counter

            return self._json_response(response_data)
        except Exception as e:
            return self._json_response({'error': str(e)}, 500)

    @http.route('/api/voice/ticket/status', type='http', auth='public', methods=['POST'], csrf=False)
    def check_status(self, **kwargs):
        """Use Case 2: Check ticket status using ticket_number with detailed stage data."""
        if not self._authenticate():
            return self._json_response({'error': 'Unauthorized'}, 401)

        try:
            payload = json.loads(request.httprequest.data)
            ticket_id = payload.get('ticket_number')

            if not ticket_id:
                return self._json_response({'error': 'Missing ticket_number'}, 400)

            ticket = request.env['helpdesk.ticket'].sudo().browse(int(ticket_id))

            if not ticket.exists():
                return self._json_response({'error': 'Ticket not found'}, 404)

            stage_name = ticket.stage_id.name or 'New'

            # Security Rule: Hide finance/payment hold stages
            if 'Payment Hold' in stage_name or 'Finance' in stage_name:
                return self._json_response({
                    'status': 'success',
                    'stage': stage_name,
                    'spoken_status': 'Your ticket is currently with our billing department. Please speak with an agent for more details.'
                })

            stage_mapping = {
                'New': 'Your ticket has been logged and is awaiting review.',
                'In Progress': 'Our technical team is currently investigating your issue.',
                'Solved': 'Your ticket has been marked as resolved.',
                'Closed': 'Your ticket has been closed.'
            }

            friendly_status = stage_mapping.get(stage_name, f"Your ticket is currently in the {stage_name} stage.")

            response_data = {
                'status': 'success',
                'stage': stage_name,
                'spoken_status': friendly_status
            }

            # Safely fetch scheduled date (checks common Helpdesk/Field Service fields)
            sched_date = getattr(ticket, 'schedule_date', False) or getattr(ticket, 'planned_date_begin',
                                                                            False) or getattr(ticket, 'date_deadline',
                                                                                              False)
            if sched_date:
                response_data['scheduled_for'] = str(sched_date)

            # Safely fetch hold reason
            hold_reason = getattr(ticket, 'hold_reason', False)
            if hold_reason:
                response_data['hold_reason'] = str(hold_reason)

            # Fetch the most recent text comment
            comments = ticket.message_ids.filtered(lambda m: m.message_type == 'comment' and m.body)
            if comments:
                response_data['latest_comment'] = html2plaintext(comments[0].body).strip()

            return self._json_response(response_data)
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

    @http.route('/api/voice/contact/search', type='http', auth='public', methods=['POST'], csrf=False)
    def search_contact(self, **kwargs):
        """Verifies if a caller exists by Customer ID or Exact Phone/Email."""
        if not self._authenticate():
            return self._json_response({'error': 'Unauthorized'}, 401)

        try:
            payload = json.loads(request.httprequest.data)
            customer_id = payload.get('customer_id') or payload.get('partner_id')
            phone = payload.get('caller_phone')
            email = payload.get('caller_email')

            partner = False

            if customer_id:
                try:
                    p = request.env['res.partner'].sudo().browse(int(customer_id))
                    if p.exists():
                        partner = p
                except (ValueError, TypeError):
                    pass

            if not partner:
                domain = []
                if phone:
                    domain.append(('phone', '=', phone))
                if email:
                    domain.append(('email', '=ilike', email.strip()))

                if len(domain) == 2:
                    domain = ['|'] + domain

                if domain:
                    partner = request.env['res.partner'].sudo().search(domain, limit=1)

            if not customer_id and not phone and not email:
                return self._json_response({'error': 'Provide customer_id, caller_phone, or caller_email'}, 400)

            if partner:
                contact_data = {
                    'id': partner.id,
                    'parent_id': partner.parent_id.id if partner.parent_id else None,
                    'name': partner.name,
                    'email': partner.email,
                    'phone': partner.phone,
                }

                if partner.fios_provision_state == 'active':
                    contact_data['fios_active'] = True
                    contact_data['fios_days_left'] = partner.fios_days_counter
                else:
                    contact_data['fios_active'] = False
                    contact_data['fios_days_left'] = None

                return self._json_response({
                    'status': 'success',
                    'found': True,
                    'contact': contact_data
                })

            return self._json_response({'status': 'success', 'found': False, 'message': 'Contact not found'})
        except Exception as e:
            return self._json_response({'error': str(e)}, 500)

    @http.route('/api/voice/grace_period/grant', type='http', auth='public', methods=['POST'], csrf=False)
    def grant_grace_period(self, **kwargs):
        """Use Case 4: Grants a 7-day FIOS grace period via voice command."""
        if not self._authenticate():
            return self._json_response({'error': 'Unauthorized'}, 401)

        try:
            payload = json.loads(request.httprequest.data)
            customer_id = payload.get('customer_id') or payload.get('partner_id')
            phone = payload.get('caller_phone')
            email = payload.get('caller_email')

            partner = False

            if customer_id:
                try:
                    p = request.env['res.partner'].sudo().browse(int(customer_id))
                    if p.exists():
                        partner = p
                except (ValueError, TypeError):
                    pass

            if not partner:
                domain = []
                if phone:
                    domain.append(('phone', '=', phone))
                if email:
                    domain.append(('email', '=ilike', email.strip()))

                if len(domain) == 2:
                    domain = ['|'] + domain

                if domain:
                    partner = request.env['res.partner'].sudo().search(domain, limit=1)

            if not partner:
                return self._json_response({'error': 'Customer not found'}, 404)

            try:
                days = request.env['fios.provisioning'].sudo().grant_grace_period(partner, source='portal')
                expiry_date = partner.fios_grace_expiry.strftime('%Y-%m-%d') if partner.fios_grace_expiry else ''

                return self._json_response({
                    'status': 'success',
                    'grace_granted': True,
                    'days_granted': days,
                    'expiry_date': expiry_date,
                    'spoken_status': f"A {days}-day grace period has been granted. Your service access has been restored until {expiry_date}."
                })
            except UserError as ue:
                return self._json_response({
                    'status': 'error',
                    'grace_granted': False,
                    'spoken_status': str(ue),
                    'error': str(ue)
                }, 400)

        except Exception as e:
            return self._json_response({'error': str(e)}, 500)
