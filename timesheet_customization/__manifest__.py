{
    'name': 'Timesheet customization',
    'summary': "Modifications for employee timesheets",
    'description': """Modifications for employee timesheets""",
    'version': '1.0.0',
    'category': '',
    'author': 'Nisus Solutions (Pvt) Ltd',
    'website': 'http://www.nisus.lk',
    'depends': [
        'timesheet_grid', 'project'
    ],
    'data': [
        'views/hr_timesheet_views.xml',
        'views/project_views.xml',
        'wizard/project_task_create_timesheet_views.xml',
        'security/hr_timesheet_security.xml',
    ],
    'installable': True,
    'auto_install': False,
}

# Actual Version 1.0.4
