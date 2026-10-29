# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

import sys
from datetime import date, timedelta

from odoo import _
from odoo import release

from .base_check import BaseCheck
from .helpers import (
    config_get,
    detect_environment,
    get_param,
    is_hashed_admin_password,
    load_supported_versions,
    parse_iso_date,
)
from .registry import register


def _platform_managed_note():
    return _(
        'This instance looks like Odoo.sh. Database manager, master password, '
        'workers and dbfilter are typically managed by the platform.'
    )


@register
class Cfg01(BaseCheck):
    code = 'CFG-01'
    area = 'config'
    severity = 'critical'
    title = _('Database manager exposed')
    why = _('When the database manager is exposed, anyone who finds the instance can list or create databases if the master password is weak.')
    recommendation = _(
        'Start Odoo with list_db = False (or --no-database-list) on production, '
        'and keep a strong hashed master password. This is what Odoo itself reports; a reverse proxy may still hide the page.'
    )
    reference = 'Server configuration'

    def run(self, env):
        if detect_environment() == 'odoosh':
            return self.outcome('passed', _platform_managed_note())
        list_db = bool(config_get('list_db', True))
        if list_db:
            return self.outcome(
                'failed',
                _('The database manager is enabled (list_db is true). Odoo will list databases on the login screen.'),
            )
        return self.outcome('passed', _('The database manager is disabled (list_db is false).'))


@register
class Cfg02(BaseCheck):
    code = 'CFG-02'
    area = 'config'
    severity = 'critical'
    title = _('Master password weak, default or in clear text')
    why = _('The master password protects the database manager. A default or clear-text value is trivial to abuse.')
    recommendation = _(
        'Set a long unique master password so that Odoo stores it as a pbkdf2 hash. '
        'The value is never shown in this report.'
    )
    reference = 'Server configuration'

    def run(self, env):
        if detect_environment() == 'odoosh':
            return self.outcome('passed', _platform_managed_note())
        passwd = config_get('admin_passwd', '') or ''
        if not passwd or str(passwd) == 'admin':
            return self.outcome(
                'failed',
                _('The master password is empty or set to the default value. The actual value is not displayed.'),
            )
        if not is_hashed_admin_password(passwd):
            return self.outcome(
                'failed',
                _('The master password is stored in clear text rather than as a pbkdf2 hash. The actual value is not displayed.'),
            )
        return self.outcome('passed', _('The master password is set and stored as a hash. The value is not displayed.'))


@register
class Cfg03(BaseCheck):
    code = 'CFG-03'
    area = 'config'
    severity = 'high'
    title = _('Database filter not set')
    why = _('Without a dbfilter, a visitor can target any database on the server when several exist.')
    recommendation = _('Set dbfilter to a host-based pattern, and disable the database manager on production.')
    reference = 'Server configuration'

    def run(self, env):
        if detect_environment() == 'odoosh':
            return self.outcome('passed', _platform_managed_note())
        dbfilter = (config_get('dbfilter', '') or '').strip()
        db_count = 1
        try:
            from odoo.service import db as db_service
            db_count = len(db_service.list_dbs(True) or [])
        except Exception:
            db_count = 1
        if not dbfilter and db_count > 1:
            return self.outcome(
                'failed',
                _('dbfilter is empty and %s databases are visible to the process.') % db_count,
            )
        if not dbfilter:
            return self.outcome(
                'warning',
                _('dbfilter is empty. This is acceptable for a single database, but should be set if more databases are added.'),
            )
        return self.outcome('passed', _('A database filter is configured.'))


@register
class Cfg04(BaseCheck):
    code = 'CFG-04'
    area = 'config'
    severity = 'medium'
    title = _('Debug or verbose logging in production')
    why = _('Debug logs and developer mode leak internals and slow the server down.')
    recommendation = _('Set log_level to info or warn, and disable --dev on production.')
    reference = 'Server configuration'

    def run(self, env):
        log_level = str(config_get('log_level', 'info') or 'info').lower()
        dev_mode = config_get('dev_mode') or False
        debug_levels = {'debug', 'debug_rpc', 'debug_sql', 'debug_rpc_answer'}
        issues = []
        if log_level in debug_levels:
            issues.append(_('log_level is %s') % log_level)
        if dev_mode:
            issues.append(_('developer mode is active'))
        if issues:
            return self.outcome('failed', _('Verbose options are on: %s.') % '; '.join(issues))
        return self.outcome('passed', _('log_level is %s and developer mode is off.') % log_level)


@register
class Cfg05(BaseCheck):
    code = 'CFG-05'
    area = 'config'
    severity = 'medium'
    title = _('Test options enabled')
    why = _('Test mode changes behaviour and can expose fixtures that do not belong in production.')
    recommendation = _('Disable test_enable and test_file on production processes.')
    reference = 'Server configuration'

    def run(self, env):
        test_enable = bool(config_get('test_enable'))
        test_file = config_get('test_file') or False
        if test_enable or test_file:
            return self.outcome(
                'failed',
                _('Test options are enabled (test_enable=%s, test_file set=%s).')
                % (bool(test_enable), bool(test_file)),
            )
        return self.outcome('passed', _('Test options are disabled.'))


@register
class Cfg06(BaseCheck):
    code = 'CFG-06'
    area = 'config'
    severity = 'medium'
    title = _('Unsafe proxy mode')
    why = _('If Odoo sits behind a reverse proxy, proxy_mode must match how forwarded headers are sent, otherwise HTTPS and client IPs are wrong.')
    recommendation = _(
        'Enable proxy_mode only when a trusted reverse proxy strips untrusted forwarded headers. '
        'This check reports what the current request and config show.'
    )
    reference = 'Server configuration'

    def run(self, env):
        proxy_mode = bool(config_get('proxy_mode'))
        forwarded = False
        try:
            from odoo.http import request
            if request and getattr(request, 'httprequest', None):
                headers = request.httprequest.headers
                forwarded = bool(headers.get('X-Forwarded-For') or headers.get('X-Forwarded-Proto'))
        except Exception:
            forwarded = False
        if forwarded and not proxy_mode:
            return self.outcome(
                'failed',
                _('Forwarded headers are present but proxy_mode is disabled. Odoo may ignore HTTPS termination.'),
            )
        if proxy_mode and not forwarded:
            return self.outcome(
                'warning',
                _('proxy_mode is enabled but this request has no forwarded headers. Confirm the reverse proxy configuration.'),
            )
        if not proxy_mode:
            return self.outcome(
                'warning',
                _('proxy_mode is disabled. Enable it if a reverse proxy terminates TLS in front of Odoo.'),
            )
        return self.outcome('passed', _('proxy_mode is enabled and forwarded headers are present on this request.'))


@register
class Cfg07(BaseCheck):
    code = 'CFG-07'
    area = 'config'
    severity = 'low'
    title = _('Threaded mode in production')
    why = _('workers = 0 runs a single threaded process, which does not scale and is not the usual production setup.')
    recommendation = _('Run Odoo with several workers behind a reverse proxy on production. Ignore this on a laptop or unit-test run.')
    reference = 'Server configuration'

    def run(self, env):
        if detect_environment() == 'odoosh':
            return self.outcome('passed', _platform_managed_note())
        workers = config_get('workers', 0) or 0
        try:
            workers = int(workers)
        except (TypeError, ValueError):
            workers = 0
        if workers <= 0:
            return self.outcome(
                'warning',
                _('workers is 0, so Odoo is in threaded mode. Use prefork workers on production.'),
            )
        return self.outcome('passed', _('Prefork workers are configured (workers=%s).') % workers)


@register
class Cfg08(BaseCheck):
    code = 'CFG-08'
    area = 'config'
    severity = 'high'
    title = _('Base URL not HTTPS')
    why = _('Links, password resets and cookies follow web.base.url. HTTP on a public host sends them in clear text.')
    recommendation = _('Set web.base.url to an https:// address and freeze it.')
    reference = 'web.base.url'

    def run(self, env):
        url = (get_param(env, 'web.base.url', '') or '').strip()
        lowered = url.lower()
        local = any(token in lowered for token in ('localhost', '127.0.0.1', '0.0.0.0'))
        if lowered.startswith('https://'):
            return self.outcome('passed', _('web.base.url uses HTTPS (%s).') % url)
        if lowered.startswith('http://') and local:
            return self.outcome(
                'warning',
                _('web.base.url is HTTP on a local host (%s), which is acceptable for development.') % url,
            )
        if lowered.startswith('http://'):
            return self.outcome('failed', _('web.base.url is HTTP on a non-local host (%s).') % url)
        return self.outcome('warning', _('web.base.url is missing or not a recognised URL (%s).') % (url or _('empty')))


@register
class Cfg09(BaseCheck):
    code = 'CFG-09'
    area = 'config'
    severity = 'low'
    title = _('Base URL not frozen')
    why = _('If web.base.url is not frozen, the first visitor can change the public URL used in emails.')
    recommendation = _('Set ir.config_parameter web.base.url.freeze to True after setting the correct URL.')
    reference = 'web.base.url.freeze'

    def run(self, env):
        frozen = str(get_param(env, 'web.base.url.freeze', '')).lower() in ('1', 'true', 'yes')
        if frozen:
            return self.outcome('passed', _('web.base.url.freeze is set.'))
        return self.outcome('failed', _('web.base.url.freeze is not set.'))


@register
class Cfg10(BaseCheck):
    code = 'CFG-10'
    area = 'config'
    severity = 'medium'
    title = _('Unencrypted outgoing mail')
    why = _('SMTP without TLS can leak message content and credentials on the network.')
    recommendation = _('Set encryption to STARTTLS or SSL/TLS on every outgoing mail server.')
    reference = 'Outgoing mail'

    def run(self, env):
        servers = env['ir.mail_server'].sudo().search_read(
            [('smtp_encryption', '=', 'none')],
            ['name', 'smtp_host', 'smtp_encryption'],
        )
        if not servers:
            return self.outcome('passed', _('No active outgoing mail server uses encryption "none".'))
        names = ', '.join((row.get('name') or row.get('smtp_host') or str(row['id'])) for row in servers[:15])
        return self.outcome(
            'failed',
            _('%s outgoing mail server(s) use no SMTP encryption: %s.') % (len(servers), names),
            'ir.mail_server',
            [row['id'] for row in servers],
        )


@register
class Cfg11(BaseCheck):
    code = 'CFG-11'
    area = 'config'
    severity = 'high'
    title = _('Odoo version support status')
    why = _('Running an unsupported Odoo version means security fixes are no longer published for that series.')
    recommendation = _('Plan an upgrade before the bundled end-of-support date. The table is shipped with the module and is not fetched from the network.')
    reference = 'Lifecycle'

    def run(self, env):
        table = load_supported_versions(env)
        series = '%s.%s' % (release.version_info[0], release.version_info[1])
        odoo_table = (table.get('odoo') or {})
        entry = odoo_table.get(series) or odoo_table.get(release.major_version) or {}
        table_date = table.get('table_date') or ''
        if not entry:
            return self.outcome(
                'warning',
                _('Odoo %s is not in the bundled support table (table date %s). Treat support status as unknown.')
                % (release.version, table_date),
            )
        eol = parse_iso_date(entry.get('eol'))
        today = date.today()
        extra = _(' Support table date: %s.') % table_date if table_date else ''
        if eol and today > eol:
            return self.outcome(
                'failed',
                _('Odoo %s is past the bundled end-of-support date (%s).%s') % (release.version, eol.isoformat(), extra),
            )
        if eol and today > eol - timedelta(days=180):
            return self.outcome(
                'warning',
                _('Odoo %s reaches bundled end of support on %s.%s') % (release.version, eol.isoformat(), extra),
            )
        return self.outcome(
            'passed',
            _('Odoo %s is within the bundled support window (until %s).%s')
            % (release.version, eol.isoformat() if eol else _('unknown'), extra),
        )


@register
class Cfg12(BaseCheck):
    code = 'CFG-12'
    area = 'config'
    severity = 'low'
    title = _('Python version support status')
    why = _('An unsupported Python runtime no longer receives interpreter security fixes.')
    recommendation = _('Run a Python version that is still in the bundled support table.')
    reference = 'Lifecycle'

    def run(self, env):
        table = load_supported_versions(env)
        series = '%s.%s' % (sys.version_info[0], sys.version_info[1])
        entry = (table.get('python') or {}).get(series) or {}
        table_date = table.get('table_date') or ''
        extra = _(' Support table date: %s.') % table_date if table_date else ''
        if not entry:
            return self.outcome(
                'warning',
                _('Python %s is not in the bundled support table.%s') % (series, extra),
            )
        eol = parse_iso_date(entry.get('eol'))
        today = date.today()
        if eol and today > eol:
            return self.outcome(
                'failed',
                _('Python %s is past the bundled end-of-support date (%s).%s') % (series, eol.isoformat(), extra),
            )
        return self.outcome(
            'passed',
            _('Python %s is within the bundled support window (until %s).%s')
            % (series, eol.isoformat() if eol else _('unknown'), extra),
        )
