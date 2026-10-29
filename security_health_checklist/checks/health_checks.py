# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

from odoo import _

from .base_check import BaseCheck
from .helpers import detect_environment, get_param, model_exists
from .registry import register


@register
class Hlt01(BaseCheck):
    code = 'HLT-01'
    area = 'health'
    severity = 'medium'
    title = _('Modules pending upgrade')
    why = _('Modules left in "to upgrade" or "to install" mean the database and code are out of step.')
    recommendation = _('Finish the upgrade or install from the Apps menu, or revert the code that triggered it.')
    reference = 'Modules'

    def run(self, env):
        rows = env['ir.module.module'].sudo().search_read(
            [('state', 'in', ['to upgrade', 'to install'])],
            ['name', 'state', 'latest_version'],
        )
        if not rows:
            return self.outcome('passed', _('No module is pending install or upgrade.'))
        sample = ', '.join('%s (%s)' % (row['name'], row['state']) for row in rows[:20])
        return self.outcome(
            'failed',
            _('%s module(s) are pending: %s.') % (len(rows), sample),
            'ir.module.module',
            [row['id'] for row in rows],
        )


@register
class Hlt02(BaseCheck):
    code = 'HLT-02'
    area = 'health'
    severity = 'medium'
    title = _('Broken module states')
    why = _('Unexpected module states often mean a failed install, uninstall or upgrade.')
    recommendation = _('Inspect the module list for "to remove" or inconsistent uninstallable modules and finish or revert the operation.')
    reference = 'Modules'

    def run(self, env):
        rows = env['ir.module.module'].sudo().search_read(
            [('state', 'in', ['to remove'])],
            ['name', 'state'],
        )
        extra = env['ir.module.module'].sudo().search_read(
            [('state', '=', 'uninstallable'), ('latest_version', '!=', False)],
            ['name', 'state', 'latest_version'],
            limit=50,
        )
        ids = [row['id'] for row in rows] + [row['id'] for row in extra]
        if not ids:
            return self.outcome('passed', _('No module is in an unexpected to-remove or leftover uninstallable state.'))
        sample = ', '.join(row['name'] for row in (rows + extra)[:20])
        return self.outcome(
            'warning',
            _('Module state issues for: %s.') % sample,
            'ir.module.module',
            ids,
        )


@register
class Hlt03(BaseCheck):
    code = 'HLT-03'
    area = 'health'
    severity = 'low'
    title = _('Failing scheduled actions')
    why = _('A cron that keeps failing may leave integrations, emails or cleanup unfinished.')
    recommendation = _('Open the scheduled action, read the log, and fix or disable it.')
    reference = 'Scheduled actions'

    def run(self, env):
        Cron = env['ir.cron']
        if 'failure_count' not in Cron._fields:
            return self.na(_('This Odoo build does not store a failure count on scheduled actions.'))
        rows = Cron.sudo().search_read(
            [('active', '=', True), ('failure_count', '>', 0)],
            ['name', 'failure_count'],
            limit=100,
        )
        if not rows:
            return self.outcome('passed', _('No active scheduled action has a failure count above zero.'))
        sample = ', '.join('%s (%s)' % (row['name'], row['failure_count']) for row in rows[:15])
        return self.outcome(
            'warning',
            _('%s active scheduled action(s) have failures: %s.') % (len(rows), sample),
            'ir.cron',
            [row['id'] for row in rows],
        )


@register
class Hlt04(BaseCheck):
    code = 'HLT-04'
    area = 'health'
    severity = 'low'
    title = _('Failed emails')
    why = _('Mails stuck in exception often mean a broken outgoing server or invalid recipients.')
    recommendation = _('Open emails in exception state, fix the mail server, and retry or cancel them.')
    reference = 'Mail'

    def run(self, env):
        if not model_exists(env, 'mail.mail'):
            return self.na(_('The mail.mail model is not available.'))
        count = env['mail.mail'].sudo().search_count([('state', '=', 'exception')])
        sample = env['mail.mail'].sudo().search([('state', '=', 'exception')], limit=50)
        if not count:
            return self.outcome('passed', _('No emails are in exception state.'))
        return self.outcome(
            'warning',
            _('%s email(s) are in exception state.') % count,
            'mail.mail',
            sample.ids,
        )


@register
class Hlt05(BaseCheck):
    code = 'HLT-05'
    area = 'health'
    severity = 'info'
    title = _('Attachment storage mode')
    why = _('Storing attachments in the database inflates backups; the filestore is the usual production choice.')
    recommendation = _('Use ir_attachment.location = file unless you have a reason to store blobs in PostgreSQL.')
    reference = 'Filestore'

    def run(self, env):
        location = get_param(env, 'ir_attachment.location', 'file') or 'file'
        return self.outcome(
            'passed',
            _('Informational: attachment location is "%s".') % location,
        )


@register
class Hlt06(BaseCheck):
    code = 'HLT-06'
    area = 'health'
    severity = 'info'
    title = _('Environment detection')
    why = _('Knowing whether the process runs on Odoo.sh or on-premise changes how configuration findings should be read.')
    recommendation = _('Use this as context for the rest of the report. Detection uses local environment only.')
    reference = 'Platform'

    def run(self, env):
        env_name = detect_environment()
        labels = {
            'odoosh': _('Odoo.sh (from local environment variables or paths)'),
            'onpremise': _('On-premise or self-managed process'),
            'unknown': _('Unknown'),
        }
        return self.outcome(
            'passed',
            _('Informational: environment is %s.') % labels.get(env_name, env_name),
        )
