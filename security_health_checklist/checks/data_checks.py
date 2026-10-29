# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

from odoo import _

from .base_check import BaseCheck
from .helpers import model_exists
from .registry import register

DEMO_LOGINS = ('demo', 'portal', 'public')
SENSITIVE_MODELS = (
    'res.partner.bank',
    'hr.employee',
    'account.payment',
    'account.bank.statement',
    'hr.payslip',
)


@register
class Data01(BaseCheck):
    code = 'DATA-01'
    area = 'data'
    severity = 'high'
    title = _('Demo data installed')
    why = _('Demo records, users and products do not belong in a production database and often include well-known logins.')
    recommendation = _('Rebuild production without demo data. Do not copy a demo database to production.')
    reference = 'Demo data'

    def run(self, env):
        modules = env['ir.module.module'].sudo().search_read(
            [('state', '=', 'installed'), ('demo', '=', True)],
            ['name', 'shortdesc'],
        )
        users = env['res.users'].sudo().search_read(
            [('login', 'in', list(DEMO_LOGINS)), ('active', '=', True)],
            ['login', 'name'],
        )
        if not modules and not users:
            return self.outcome('passed', _('No installed module reports demo data, and no known demo logins are active.'))
        names = ', '.join(row['name'] for row in modules[:20]) or _('none')
        logins = ', '.join(row['login'] for row in users) or _('none')
        return self.outcome(
            'failed',
            _('Demo data is present. Modules with demo flag: %s. Known demo logins: %s.') % (names, logins),
            'ir.module.module' if modules else 'res.users',
            [row['id'] for row in (modules or users)],
        )


@register
class Data02(BaseCheck):
    code = 'DATA-02'
    area = 'data'
    severity = 'medium'
    title = _('Public attachments')
    why = _('Attachments marked public can be downloaded without a login if their URL is known or guessed.')
    recommendation = _('Review public attachments that are not website or asset files and uncheck Public where it is not needed.')
    reference = 'Attachments'

    def run(self, env):
        domain = [
            ('public', '=', True),
            '|', ('url', '=', False), '!', ('url', '=like', '/web/assets%'),
            '!', ('name', '=like', 'web.assets%'),
        ]
        count = env['ir.attachment'].sudo().search_count(domain)
        sample = env['ir.attachment'].sudo().search_read(domain, ['name', 'mimetype'], limit=30)
        if not count:
            return self.outcome('passed', _('No public attachments were found outside web assets.'))
        names = ', '.join((row.get('name') or str(row['id'])) for row in sample[:10])
        return self.outcome(
            'warning' if count < 20 else 'failed',
            _('%s public attachment(s) outside web assets. Sample: %s.') % (count, names),
            'ir.attachment',
            [row['id'] for row in sample],
        )


@register
class Data03(BaseCheck):
    code = 'DATA-03'
    area = 'data'
    severity = 'low'
    title = _('Sensitive models without record rules')
    why = _('Access control lists without record rules mean every user of a group can see all records of that model.')
    recommendation = _(
        'Add record rules for sensitive models such as bank accounts and employees, matching how those apps are used.'
    )
    reference = 'Record rules'

    def run(self, env):
        missing = []
        model_ids = []
        for name in SENSITIVE_MODELS:
            if not model_exists(env, name):
                continue
            model = env['ir.model'].sudo().search([('model', '=', name)], limit=1)
            if not model:
                continue
            rules = env['ir.rule'].sudo().search_count([('model_id', '=', model.id)])
            if not rules:
                missing.append(name)
                model_ids.append(model.id)
        if not missing:
            return self.outcome(
                'passed',
                _('Installed sensitive models in the advisory list have at least one record rule, or are not installed.'),
            )
        return self.outcome(
            'warning',
            _('Advisory: these sensitive models have access rights but no record rules: %s.') % ', '.join(missing),
            'ir.model',
            model_ids,
        )


@register
class Data04(BaseCheck):
    code = 'DATA-04'
    area = 'data'
    severity = 'high'
    title = _('Global ACL entries open to everyone')
    why = _('An access line with no group and write, create or unlink rights lets every user change that model.')
    recommendation = _('Remove or group-restrict ir.model.access lines that grant write, create or unlink without a group.')
    reference = 'Access control'

    def run(self, env):
        domain = [
            ('group_id', '=', False),
            '|', '|',
            ('perm_write', '=', True),
            ('perm_create', '=', True),
            ('perm_unlink', '=', True),
        ]
        rows = env['ir.model.access'].sudo().search_read(
            domain,
            ['name', 'model_id', 'perm_write', 'perm_create', 'perm_unlink'],
            limit=200,
        )
        if not rows:
            return self.outcome('passed', _('No global ACL line grants write, create or unlink to everyone.'))
        names = ', '.join((row.get('name') or str(row['id'])) for row in rows[:15])
        return self.outcome(
            'failed',
            _('%s global ACL line(s) grant write, create or unlink without a group. Sample: %s.')
            % (len(rows), names),
            'ir.model.access',
            [row['id'] for row in rows],
        )
