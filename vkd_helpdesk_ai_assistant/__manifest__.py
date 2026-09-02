{
    'name': "Helpdesk Voice Integration (Iris AI)",
    'version': '19.0.1.0.3',
    'category': 'Helpdesk',
    'summary': 'Custom REST endpoints for Iris Voice AI Helpdesk integration',
    'description': """
        This module provides custom REST API endpoints for the KLOUDIP Iris voice assistant.
        - Endpoint for logging a new query
        - Endpoint for checking ticket status with caller verification[
        - Endpoint for adding a voice-transcribed comment to a ticket thread
    """,
    'author': "VK Data ApS",
    'website': "https://vkdata.dk",
    'depends': ['base', 'helpdesk', 'mail'],
    'data': [],
    'demo': [],
    'license': 'OPL-1',
    'application': False,
    'installable': True,
    'auto_install': False,
}
