# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

import json
import os
from datetime import datetime

from odoo.tools import config as odoo_config

MODULE_NAME = 'security_health_checklist'

GENERIC_LOGINS = frozenset({
    'admin', 'administrator', 'info', 'test', 'demo', 'user', 'root',
    'support', 'guest', 'odoo',
})

DEFAULT_BRUTEFORCE_MODULES = (
    'auth_brute_force',
    'auth_signup_verify_email',
    'password_security',
)


def get_param(env, key, default=''):
    value = env['ir.config_parameter'].sudo().get_param(key, default)
    return default if value in (None, False, '') else value


def get_param_int(env, key, default=0):
    try:
        return int(get_param(env, key, default))
    except (TypeError, ValueError):
        return default


def is_module_installed(env, xmlid_or_name):
    return bool(env['ir.module.module'].sudo().search_count([
        ('name', '=', xmlid_or_name),
        ('state', '=', 'installed'),
    ]))


def get_settings_users(env):
    group = env.ref('base.group_system', raise_if_not_found=False)
    if not group:
        return env['res.users']
    field_name = 'group_ids' if 'group_ids' in env['res.users']._fields else 'groups_id'
    return env['res.users'].sudo().search([
        (field_name, 'in', [group.id]),
        ('share', '=', False),
        ('active', '=', True),
    ])


def module_owned_ids(env, model_name):
    return env['ir.model.data'].sudo().search([
        ('module', '=', MODULE_NAME),
        ('model', '=', model_name),
    ]).mapped('res_id')


def detect_environment():
    if os.environ.get('ODOO_STAGE') or os.environ.get('ODOO_SH'):
        return 'odoosh'
    if os.path.isdir('/home/odoo/src/user') or os.path.isdir('/home/odoo/src/odoo'):
        return 'odoosh'
    return 'onpremise'


def detect_edition(env):
    if is_module_installed(env, 'web_enterprise'):
        return 'enterprise'
    return 'community'


def is_hashed_admin_password(value):
    if not value:
        return False
    text = str(value)
    return text.startswith('$pbkdf2-sha512$') or text.startswith('$pbkdf2-sha256$')


def parse_iso_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    text = str(value)[:10]
    try:
        return datetime.strptime(text, '%Y-%m-%d').date()
    except ValueError:
        return None


def load_supported_versions(env):
    raw = get_param(env, 'shc.supported_versions', '{}')
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def truncate(text, length=160):
    text = (text or '').replace('\n', ' ').strip()
    if len(text) <= length:
        return text
    return text[: length - 1] + '…'


def field_exists(env, model_name, field_name):
    if model_name not in env:
        return False
    return field_name in env[model_name]._fields


def model_exists(env, model_name):
    return model_name in env.registry


def config_get(key, default=None):
    try:
        return odoo_config.get(key, default)
    except Exception:
        return default
