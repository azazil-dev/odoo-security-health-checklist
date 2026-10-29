# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

import re
from datetime import timedelta

from odoo import _, fields

from .base_check import BaseCheck
from .helpers import get_settings_users, is_module_installed, model_exists, module_owned_ids, truncate
from .registry import register

RISKY_PATTERNS = (
    re.compile(r'os\.system'),
    re.compile(r'subprocess'),
    re.compile(r'\beval\s*\('),
    re.compile(r'\bexec\s*\('),
    re.compile(r'__import__'),
    re.compile(r'cr\.execute\s*\([^)]*%'),
    re.compile(r'cr\.execute\s*\([^)]*\.format'),
)

ODOO_AUTHOR_HINTS = ('odoo s.a.', 'odoo sa', 'openerp')


def _code_actions(env):
    exclude = set(module_owned_ids(env, 'ir.actions.server'))
    exclude.update(module_owned_ids(env, 'ir.cron'))
    domain = [('state', '=', 'code')]
    rows = env['ir.actions.server'].sudo().search_read(
        domain,
        ['name', 'code', 'write_date', 'model_id'],
        limit=500,
    )
    return [row for row in rows if row['id'] not in exclude and (row.get('code') or '').strip()]


@register
class Code01(BaseCheck):
    code = 'CODE-01'
    area = 'code'
    severity = 'high'
    title = _('Server actions executing Python code')
    why = _('Python server actions can be edited from the UI and run with the rights of their user.')
    recommendation = _('Review each code action, restrict who can edit Technical Features, and prefer coded modules over UI Python.')
    reference = 'Server actions'

    def run(self, env):
        rows = _code_actions(env)
        if not rows:
            return self.outcome('passed', _('No server actions with Python code were found (module-owned actions are ignored).'))
        names = ', '.join((row.get('name') or str(row['id'])) for row in rows[:15])
        return self.outcome(
            'failed',
            _('%s server action(s) execute Python code: %s. Code is not executed by this check.')
            % (len(rows), names),
            'ir.actions.server',
            [row['id'] for row in rows],
        )


@register
class Code02(BaseCheck):
    code = 'CODE-02'
    area = 'code'
    severity = 'high'
    title = _('Automated actions running Python code')
    why = _('Automated actions that call Python run on everyday events and are easy to overlook.')
    recommendation = _('Review automations that call code server actions and disable those that are not required.')
    reference = 'Automated actions'

    def applicable(self, env):
        return is_module_installed(env, 'base_automation') and model_exists(env, 'base.automation')

    def run(self, env):
        exclude = set(module_owned_ids(env, 'base.automation'))
        code_action_ids = [row['id'] for row in _code_actions(env)]
        linked_ids = []
        names = []
        Server = env['ir.actions.server'].sudo()
        if 'base_automation_id' in Server._fields and code_action_ids:
            rows = Server.search_read(
                [('id', 'in', code_action_ids), ('base_automation_id', '!=', False)],
                ['name', 'base_automation_id'],
                limit=500,
            )
            for row in rows:
                auto_id = row['base_automation_id'][0]
                if auto_id in exclude:
                    continue
                if auto_id not in linked_ids:
                    linked_ids.append(auto_id)
                    names.append(row['base_automation_id'][1])
        elif 'action_server_id' in env['base.automation']._fields:
            rows = env['base.automation'].sudo().search_read(
                [('action_server_id', 'in', code_action_ids)],
                ['name'],
                limit=500,
            )
            for row in rows:
                if row['id'] in exclude:
                    continue
                linked_ids.append(row['id'])
                names.append(row.get('name') or str(row['id']))
        if not linked_ids:
            return self.outcome('passed', _('No automated action is linked to a Python server action.'))
        return self.outcome(
            'failed',
            _('%s automated action(s) run Python code: %s.') % (len(linked_ids), ', '.join(names[:15])),
            'base.automation',
            linked_ids,
        )


@register
class Code03(BaseCheck):
    code = 'CODE-03'
    area = 'code'
    severity = 'medium'
    title = _('Code actions modified recently')
    why = _('A recent edit to UI Python is a useful audit signal, especially if several people have Technical Features.')
    recommendation = _('Review the chatter and write date of recently modified code actions.')
    reference = 'Server actions'

    def run(self, env):
        cutoff = fields.Datetime.now() - timedelta(days=30)
        rows = [row for row in _code_actions(env) if row.get('write_date') and row['write_date'] >= cutoff]
        if not rows:
            return self.outcome('passed', _('No Python server actions were modified in the last 30 days.'))
        names = ', '.join((row.get('name') or str(row['id'])) for row in rows[:15])
        return self.outcome(
            'warning',
            _('%s Python server action(s) were modified in the last 30 days: %s.') % (len(rows), names),
            'ir.actions.server',
            [row['id'] for row in rows],
        )


@register
class Code04(BaseCheck):
    code = 'CODE-04'
    area = 'code'
    severity = 'medium'
    title = _('Scheduled actions running as a privileged user')
    why = _('A cron running as a Settings user executes with full rights, including any Python it calls.')
    recommendation = _('Run scheduled actions as a dedicated user with the least rights needed.')
    reference = 'Scheduled actions'

    def run(self, env):
        exclude = set(module_owned_ids(env, 'ir.cron'))
        admin_ids = set(get_settings_users(env).ids)
        fields_list = ['name', 'user_id', 'active']
        Cron = env['ir.cron'].sudo()
        if 'state' in Cron._fields:
            fields_list.append('state')
        if 'code' in Cron._fields:
            fields_list.append('code')
        if 'ir_actions_server_id' in Cron._fields:
            fields_list.append('ir_actions_server_id')
        rows = Cron.search_read([('active', '=', True)], fields_list, limit=500)
        risky = []
        for row in rows:
            if row['id'] in exclude:
                continue
            user = row.get('user_id')
            if not user or user[0] not in admin_ids:
                continue
            state = row.get('state')
            code = (row.get('code') or '').strip()
            if state == 'code' or code:
                risky.append(row)
        if not risky:
            return self.outcome(
                'passed',
                _('No active scheduled action runs Python (or a code server action) as a Settings user. '
                  'This module\'s own cron is ignored.'),
            )
        names = ', '.join((row.get('name') or str(row['id'])) for row in risky[:15])
        return self.outcome(
            'failed',
            _('%s scheduled action(s) run code as a Settings user: %s.') % (len(risky), names),
            'ir.cron',
            [row['id'] for row in risky],
        )


@register
class Code05(BaseCheck):
    code = 'CODE-05'
    area = 'code'
    severity = 'medium'
    title = _('Risky code patterns (advisory)')
    why = _('Some Python patterns (process calls, eval, dynamic SQL) are dangerous if they appear in UI-edited actions.')
    recommendation = _(
        'Rewrite matching actions in a reviewed module. This check only searches text; it never executes the code. '
        'Matches can be false positives.'
    )
    reference = 'Server actions / advisory'

    def run(self, env):
        hits = []
        excerpts = []
        for row in _code_actions(env):
            code = row.get('code') or ''
            matched_line = None
            for line in code.splitlines():
                if any(pattern.search(line) for pattern in RISKY_PATTERNS):
                    matched_line = truncate(line, 120)
                    break
            if matched_line:
                hits.append(row)
                excerpts.append('%s: %s' % (row.get('name') or row['id'], matched_line))
        if not hits:
            return self.outcome('passed', _('No advisory risky patterns were found in Python server actions.'))
        return self.outcome(
            'warning',
            _('Advisory: %s server action(s) match risky patterns. Matching lines: %s')
            % (len(hits), ' | '.join(excerpts[:8])),
            'ir.actions.server',
            [row['id'] for row in hits],
        )


@register
class Code06(BaseCheck):
    code = 'CODE-06'
    area = 'code'
    severity = 'info'
    title = _('Custom and third-party modules installed')
    why = _('Third-party code is part of the security surface. This check is informational and never treats a license as a finding.')
    recommendation = _('Keep an inventory of non-Odoo modules, their authors and licenses, and review them on upgrade.')
    reference = 'Modules'

    def run(self, env):
        rows = env['ir.module.module'].sudo().search_read(
            [('state', '=', 'installed')],
            ['name', 'author', 'license', 'shortdesc'],
        )
        custom = []
        for row in rows:
            author = (row.get('author') or '').lower()
            if any(hint in author for hint in ODOO_AUTHOR_HINTS):
                continue
            if row['name'] in ('base', 'web'):
                continue
            custom.append(row)
        if not custom:
            return self.outcome('passed', _('No installed module has an author other than Odoo S.A.'))
        sample = ', '.join(
            '%s (%s, %s)' % (row['name'], row.get('author') or '?', row.get('license') or '?')
            for row in custom[:20]
        )
        return self.outcome(
            'passed',
            _('Informational: %s installed module(s) are not authored by Odoo S.A.: %s.')
            % (len(custom), sample),
            'ir.module.module',
            [row['id'] for row in custom],
        )


@register
class Code07(BaseCheck):
    code = 'CODE-07'
    area = 'code'
    severity = 'info'
    title = _('Studio customizations present')
    why = _('Studio automations and views are extra custom code. This check is informational and Enterprise-only.')
    recommendation = _('Review Studio customizations on upgrade and keep a list of what they change.')
    reference = 'Studio'

    def applicable(self, env):
        return is_module_installed(env, 'web_studio')

    def run(self, env):
        data = env['ir.model.data'].sudo().search_read(
            [('module', '=', 'studio_customization')],
            ['model', 'res_id', 'name'],
            limit=200,
        )
        if not data:
            return self.outcome('passed', _('Studio is installed but no studio_customization data was found.'))
        models = sorted({row['model'] for row in data})
        return self.outcome(
            'passed',
            _('Informational: %s Studio customization record(s) across models: %s.')
            % (len(data), ', '.join(models[:15])),
        )
