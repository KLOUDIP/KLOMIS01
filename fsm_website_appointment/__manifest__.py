# -*- coding: utf-8 -*-
{
    'name': "FSM Task from Website Appointment",
    'version': '19.0.2.0.0',
    'summary': 'Generates Field Service Tasks from Website Appointments',
    'description': """This module creates a field service task automatically whenever a new appointment is scheduled via the website.""",
    'category': 'Services/Field Service',
    'author': 'BitBrainHub',
    'maintainer': 'BitBrainHub',
    'depends': ['appointment', 'industry_fsm', 'calendar'],
    'data': [
        'views/appointment_type_views.xml',
        'views/calendar_event_views.xml',
        'views/project_task_views.xml'
    ],
    'license': 'OPL-1',
    'application': False,
    'installable': True,
    'auto_install': False,
}
