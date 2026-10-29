# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

from datetime import timedelta

from odoo import _, fields

from .base_check import BaseCheck
from .helpers import (
    DEFAULT_BRUTEFORCE_MODULES,
    GENERIC_LOGINS,
    get_param,
    get_param_int,
    get_settings_users,
    is_module_installed,
)
from .registry import register


@register
class Auth01(BaseCheck):
    code = 'AUTH-01'
    area = 'auth'
    severity = 'critical'
    title = _('Administrators without two-factor authentication')
    why = _(
        'A stolen password is enough to take over the database if Settings '
        'users do not use two-factor authentication.'
    )
    recommendation = _(
        'Enable 2FA for every user in the Settings group and require enrolment '
        'on next login.'
    )
    reference = 'Authentication / 2FA'

    def applicable(self, env):
        return is_module_installed(env, 'auth_totp')

    def run(self, env):
        users = get_settings_users(env)
        if 'totp_enabled' not in env['res.users']._fields:
            return self.na(_('The two-factor field is not available on users in this build.'))
        rows = env['res.users'].sudo().search_read(
            [('id', 'in', users.ids)],
            ['name', 'login', 'totp_enabled'],
        )
        missing = [row for row in rows if not row.get('totp_enabled')]
        if not missing:
            return self.outcome(
                'passed',
                _('All %s Settings users have two-factor authentication enabled.') % len(rows),
            )
        names = ', '.join(row['login'] for row in missing[:20])
        return self.outcome(
            'failed',
            _('%s Settings user(s) have 2FA disabled: %s.') % (len(missing), names),
            'res.users',
            [row['id'] for row in missing],
        )


@register
class Auth02(BaseCheck):
    code = 'AUTH-02'
    area = 'auth'
    severity = 'high'
    title = _('Two-factor authentication module not installed')
    why = _('Without the 2FA app, administrators cannot protect Settings accounts with a second factor.')
    recommendation = _('Install the authentication_totp (auth_totp) module and enrol Settings users.')
    reference = 'Authentication / 2FA'

    def run(self, env):
        if is_module_installed(env, 'auth_totp'):
            return self.outcome('passed', _('The two-factor authentication module is installed.'))
        return self.outcome(
            'failed',
            _('Module auth_totp is not installed. Administrators cannot enable 2FA.'),
            'ir.module.module',
            env['ir.module.module'].sudo().search([('name', '=', 'auth_totp')]).ids,
        )


@register
class Auth03(BaseCheck):
    code = 'AUTH-03'
    area = 'auth'
    severity = 'medium'
    title = _('Default administrator login')
    why = _('The login name "admin" is the first target of automated attacks.')
    recommendation = _(
        'Rename the Settings user login away from "admin" and keep a unique, non-guessable login.'
    )
    reference = 'Access'

    def run(self, env):
        users = get_settings_users(env)
        rows = env['res.users'].sudo().search_read(
            [('id', 'in', users.ids), ('login', '=', 'admin')],
            ['name', 'login'],
        )
        if not rows:
            return self.outcome('passed', _('No active Settings user uses the login "admin".'))
        return self.outcome(
            'failed',
            _('Active Settings user(s) still use the default login "admin".'),
            'res.users',
            [row['id'] for row in rows],
        )


@register
class Auth04(BaseCheck):
    code = 'AUTH-04'
    area = 'auth'
    severity = 'medium'
    title = _('Too many administrators')
    why = _('Each extra Settings user increases the chance of a privileged account being compromised.')
    recommendation = _(
        'Keep Settings rights for the smallest group that needs them. Use lesser groups for daily work.'
    )
    reference = 'Access'

    def run(self, env):
        threshold = get_param_int(env, 'shc.admin_threshold', 3)
        users = get_settings_users(env)
        count = len(users)
        if count <= threshold:
            return self.outcome(
                'passed',
                _('There are %s Settings users, which is within the threshold of %s.') % (count, threshold),
                'res.users',
                users.ids,
            )
        return self.outcome(
            'failed',
            _('There are %s Settings users, above the threshold of %s.') % (count, threshold),
            'res.users',
            users.ids,
        )


@register
class Auth05(BaseCheck):
    code = 'AUTH-05'
    area = 'auth'
    severity = 'medium'
    title = _('Dormant administrators')
    why = _('Unused privileged accounts are a quiet path into the database if their password leaks.')
    recommendation = _(
        'Archive Settings users who no longer need access, or remove the Settings group from them.'
    )
    reference = 'Access'

    def run(self, env):
        days = get_param_int(env, 'shc.dormant_days', 90)
        users = get_settings_users(env)
        cutoff = fields.Datetime.now() - timedelta(days=days)
        fields_list = ['name', 'login', 'login_date']
        rows = env['res.users'].sudo().search_read([('id', 'in', users.ids)], fields_list)
        dormant = []
        for row in rows:
            login_date = row.get('login_date')
            if not login_date or login_date < cutoff:
                dormant.append(row)
        if not dormant:
            return self.outcome(
                'passed',
                _('All Settings users have logged in within the last %s days.') % days,
            )
        return self.outcome(
            'failed',
            _('%s Settings user(s) have not logged in for more than %s days, or never logged in.')
            % (len(dormant), days),
            'res.users',
            [row['id'] for row in dormant],
        )


@register
class Auth06(BaseCheck):
    code = 'AUTH-06'
    area = 'auth'
    severity = 'medium'
    title = _('Password policy too weak')
    why = _('Short passwords are easier to guess and reuse. A minimum of 12 characters is a common baseline.')
    recommendation = _(
        'Install a password policy app if needed and set auth_password_policy.minlength to 12 or more. '
        'This check never tests actual passwords.'
    )
    reference = 'Password policy'

    def run(self, env):
        raw = get_param(env, 'auth_password_policy.minlength', '')
        try:
            length = int(raw) if raw not in (None, '', False) else 0
        except ValueError:
            length = 0
        if length >= 12:
            return self.outcome('passed', _('Minimum password length is %s characters.') % length)
        if not raw:
            return self.outcome(
                'failed',
                _('No minimum password length is configured (expected at least 12).'),
            )
        return self.outcome(
            'failed',
            _('Minimum password length is %s characters (expected at least 12).') % length,
        )


@register
class Auth07(BaseCheck):
    code = 'AUTH-07'
    area = 'auth'
    severity = 'medium'
    title = _('Open or loose public sign-up')
    why = _('Open sign-up lets anyone create a user. That is rarely appropriate on a production database.')
    recommendation = _(
        'Set invitation scope to invitation-only, or disable public sign-up if the Sign Up app is not needed.'
    )
    reference = 'Sign-up'

    def run(self, env):
        if not is_module_installed(env, 'auth_signup'):
            return self.na(_('The sign-up module is not installed.'))
        scope = get_param(env, 'auth_signup.invitation_scope', 'b2b')
        uninvited = get_param(env, 'auth_signup.allow_uninvited', 'False')
        open_signup = str(scope).lower() in ('b2c', 'public') or str(uninvited).lower() in ('true', '1')
        if open_signup:
            return self.outcome(
                'failed',
                _('Public sign-up is open (invitation_scope=%s, allow_uninvited=%s).')
                % (scope, uninvited),
            )
        return self.outcome(
            'passed',
            _('Sign-up is restricted (invitation_scope=%s).') % scope,
        )


@register
class Auth08(BaseCheck):
    code = 'AUTH-08'
    area = 'auth'
    severity = 'low'
    title = _('Generic accounts with high privileges')
    why = _('Logins such as info, demo or test are easy to guess and often shared.')
    recommendation = _('Replace generic privileged logins with named personal accounts.')
    reference = 'Access'

    def run(self, env):
        users = get_settings_users(env)
        rows = env['res.users'].sudo().search_read(
            [('id', 'in', users.ids)],
            ['name', 'login'],
        )
        generic = [row for row in rows if (row.get('login') or '').lower() in GENERIC_LOGINS]
        if not generic:
            return self.outcome('passed', _('No Settings user uses a generic login name.'))
        names = ', '.join(row['login'] for row in generic)
        return self.outcome(
            'warning',
            _('Generic privileged login(s) found: %s.') % names,
            'res.users',
            [row['id'] for row in generic],
        )


@register
class Auth09(BaseCheck):
    code = 'AUTH-09'
    area = 'auth'
    severity = 'high'
    title = _('Brute-force protection not detected')
    why = _('Without rate limiting, login forms can be attacked by guessing passwords. This check does not try any password.')
    recommendation = _(
        'Install a login rate-limiting module and also rate-limit at the reverse proxy or fail2ban. '
        'Odoo cannot see protection that lives only in front of the application.'
    )
    reference = 'Authentication / brute force'

    def run(self, env):
        raw = get_param(env, 'shc.bruteforce_modules', ','.join(DEFAULT_BRUTEFORCE_MODULES))
        names = [part.strip() for part in str(raw).split(',') if part.strip()]
        installed = env['ir.module.module'].sudo().search_read(
            [('name', 'in', names), ('state', '=', 'installed')],
            ['name'],
        )
        if installed:
            found = ', '.join(row['name'] for row in installed)
            return self.outcome(
                'passed',
                _('Known login-protection module(s) installed: %s. Also keep protection at the reverse proxy.')
                % found,
                'ir.module.module',
                [row['id'] for row in installed],
            )
        return self.outcome(
            'failed',
            _('No known login rate-limiting module is installed (%s). '
              'This does not prove that the reverse proxy is unprotected.')
            % ', '.join(names),
        )
