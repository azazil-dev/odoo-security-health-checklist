# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

{
    'name': 'Security Healthcheck',
    'summary': 'Security and health score, grade and PDF report for your Odoo instance',
    'description': """
Run a read-only security and health assessment of your Odoo 18 instance.
You get a score from 0 to 100, a grade from A to F, findings in plain language
and a branded PDF report. The scan never changes settings, never guesses
passwords and never calls the internet.
    """,
    'version': '18.0.1.0.0',
    'category': 'Administration',
    'author': 'Arif N Ramadhan',
    'website': 'https://www.niits.id',
    'maintainer': 'Arif N Ramadhan',
    'support': 'sqlrif@gmail.com',
    'license': 'OPL-1',
    'depends': ['base', 'mail'],
    'data': [
        'security/shc_security.xml',
        'security/ir.model.access.csv',
        'data/shc_sequence.xml',
        'data/shc_cron.xml',
        'data/supported_versions.xml',
        'views/shc_run_wizard_views.xml',
        'views/shc_scan_views.xml',
        'views/shc_scan_result_views.xml',
        'views/shc_config_views.xml',
        'views/shc_menus.xml',
        'report/shc_report.xml',
        'report/shc_report_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'security_health_checklist/static/src/css/shc.css',
        ],
    },
    'images': ['static/description/banner.png'],
    'application': True,
    'installable': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
    'price': 0.0,
    'currency': 'EUR',
}
