# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

class BaseCheck:
    code = ''
    area = ''
    severity = 'medium'
    title = ''
    why = ''
    recommendation = ''
    reference = ''

    def applicable(self, env):
        return True

    def run(self, env):
        raise NotImplementedError

    def na(self, found):
        return {
            'status': 'na',
            'found': found,
            'affected_model': False,
            'affected_ids': [],
        }

    def outcome(self, status, found, affected_model=None, affected_ids=None):
        return {
            'status': status,
            'found': found,
            'affected_model': affected_model or False,
            'affected_ids': list(affected_ids or []),
        }
