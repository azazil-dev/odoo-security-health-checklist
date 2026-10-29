# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

from datetime import timedelta

from odoo import _, fields

from .base_check import BaseCheck
from .helpers import get_param_int, get_settings_users, model_exists
from .registry import register

APIKEY_MODEL = 'res.users.apikeys'


def _apikey_fields(env):
    model = env[APIKEY_MODEL]
    fields_list = ['name', 'user_id', 'create_date']
    if 'expiration_date' in model._fields:
        fields_list.append('expiration_date')
    if 'scope' in model._fields:
        fields_list.append('scope')
    return fields_list


@register
class Api01(BaseCheck):
    code = 'API-01'
    area = 'api'
    severity = 'medium'
    title = _('Old API keys')
    why = _('API keys that never rotate remain valid if they leak.')
    recommendation = _('Revoke keys older than your rotation policy (default 180 days) and create new ones.')
    reference = 'API keys'

    def applicable(self, env):
        return model_exists(env, APIKEY_MODEL)

    def run(self, env):
        days = get_param_int(env, 'shc.api_key_max_age_days', 180)
        cutoff = fields.Datetime.now() - timedelta(days=days)
        rows = env[APIKEY_MODEL].sudo().search_read(
            [('create_date', '<', cutoff)],
            _apikey_fields(env),
            limit=200,
        )
        if not rows:
            return self.outcome('passed', _('No API keys older than %s days were found. Key values are not displayed.') % days)
        names = ', '.join((row.get('name') or _('unnamed')) for row in rows[:15])
        return self.outcome(
            'failed',
            _('%s API key(s) are older than %s days: %s. Key values are not displayed.')
            % (len(rows), days, names),
            APIKEY_MODEL,
            [row['id'] for row in rows],
        )


@register
class Api02(BaseCheck):
    code = 'API-02'
    area = 'api'
    severity = 'medium'
    title = _('API keys without expiration')
    why = _('Keys that never expire remain usable after the owner leaves.')
    recommendation = _('Set an expiration date on every API key, or revoke unused keys.')
    reference = 'API keys'

    def applicable(self, env):
        return model_exists(env, APIKEY_MODEL)

    def run(self, env):
        if 'expiration_date' not in env[APIKEY_MODEL]._fields:
            return self.na(_('This Odoo build does not store an expiration date on API keys.'))
        rows = env[APIKEY_MODEL].sudo().search_read(
            [('expiration_date', '=', False)],
            _apikey_fields(env),
            limit=200,
        )
        if not rows:
            return self.outcome('passed', _('Every API key has an expiration date. Key values are not displayed.'))
        names = ', '.join((row.get('name') or _('unnamed')) for row in rows[:15])
        return self.outcome(
            'failed',
            _('%s API key(s) have no expiration date: %s. Key values are not displayed.') % (len(rows), names),
            APIKEY_MODEL,
            [row['id'] for row in rows],
        )


@register
class Api03(BaseCheck):
    code = 'API-03'
    area = 'api'
    severity = 'high'
    title = _('API keys owned by inactive or dormant users')
    why = _('A key on an archived or unused account often outlives the person who created it.')
    recommendation = _('Revoke API keys whose owner is archived or has not logged in recently.')
    reference = 'API keys'

    def applicable(self, env):
        return model_exists(env, APIKEY_MODEL)

    def run(self, env):
        days = get_param_int(env, 'shc.dormant_days', 90)
        cutoff = fields.Datetime.now() - timedelta(days=days)
        keys = env[APIKEY_MODEL].sudo().search_read([], _apikey_fields(env), limit=500)
        user_ids = list({row['user_id'][0] for row in keys if row.get('user_id')})
        users = {
            row['id']: row
            for row in env['res.users'].sudo().with_context(active_test=False).search_read(
                [('id', 'in', user_ids)],
                ['name', 'login', 'active', 'login_date'],
            )
        }
        bad = []
        for row in keys:
            user = users.get(row['user_id'][0]) if row.get('user_id') else None
            if not user:
                bad.append(row)
                continue
            if not user.get('active'):
                bad.append(row)
                continue
            login_date = user.get('login_date')
            if not login_date or login_date < cutoff:
                bad.append(row)
        if not bad:
            return self.outcome('passed', _('No API keys belong to archived or dormant users. Key values are not displayed.'))
        names = ', '.join((row.get('name') or _('unnamed')) for row in bad[:15])
        return self.outcome(
            'failed',
            _('%s API key(s) belong to inactive or dormant users: %s. Key values are not displayed.')
            % (len(bad), names),
            APIKEY_MODEL,
            [row['id'] for row in bad],
        )


@register
class Api04(BaseCheck):
    code = 'API-04'
    area = 'api'
    severity = 'medium'
    title = _('API keys owned by administrators')
    why = _('A leaked administrator API key is equivalent to a Settings session without 2FA.')
    recommendation = _('Prefer keys on dedicated integration users with the least rights needed.')
    reference = 'API keys'

    def applicable(self, env):
        return model_exists(env, APIKEY_MODEL)

    def run(self, env):
        admin_ids = set(get_settings_users(env).ids)
        keys = env[APIKEY_MODEL].sudo().search_read([], _apikey_fields(env), limit=500)
        bad = [row for row in keys if row.get('user_id') and row['user_id'][0] in admin_ids]
        if not bad:
            return self.outcome('passed', _('No API keys belong to Settings users. Key values are not displayed.'))
        names = ', '.join((row.get('name') or _('unnamed')) for row in bad[:15])
        return self.outcome(
            'warning',
            _('%s API key(s) belong to Settings users: %s. Key values are not displayed.') % (len(bad), names),
            APIKEY_MODEL,
            [row['id'] for row in bad],
        )


@register
class Api05(BaseCheck):
    code = 'API-05'
    area = 'api'
    severity = 'info'
    title = _('Active external integration endpoints')
    why = _('Outbound webhooks and similar automations increase the attack surface. This check is informational.')
    recommendation = _('Review webhook automations and disable those that are unused.')
    reference = 'Integrations'

    def run(self, env):
        ids = []
        notes = []
        if model_exists(env, 'base.automation'):
            domain = []
            Automation = env['base.automation'].sudo()
            if 'webhook_uuid' in Automation._fields:
                domain = [('webhook_uuid', '!=', False)]
            elif 'state' in Automation._fields:
                domain = [('state', 'in', ['webhook', 'webhook_notification'])]
            if domain:
                rows = Automation.search_read(domain, ['name'], limit=100)
                ids = [row['id'] for row in rows]
                notes.append(_('%s webhook-type automation(s).') % len(rows))
        state_field = env['ir.actions.server']._fields.get('state') if model_exists(env, 'ir.actions.server') else None
        selection = getattr(state_field, 'selection', None) if state_field else None
        if callable(selection):
            selection = selection(env['ir.actions.server'])
        if selection and any(value == 'webhook' for value, _label in selection):
            rows = env['ir.actions.server'].sudo().search_read(
                [('state', '=', 'webhook')],
                ['name'],
                limit=100,
            )
            ids.extend(row['id'] for row in rows)
            notes.append(_('%s webhook server action(s).') % len(rows))
        if not notes:
            return self.outcome('passed', _('No webhook-type automations were detected (or the feature is not installed).'))
        return self.outcome(
            'passed',
            _('Informational: %s') % ' '.join(notes),
            'base.automation' if model_exists(env, 'base.automation') else 'ir.actions.server',
            ids,
        )
