# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

CHECKS = {}


def register(cls):
    if not getattr(cls, 'code', None):
        raise ValueError('Check class %s is missing a code' % cls)
    CHECKS[cls.code] = cls
    return cls


def iter_check_classes():
    return [CHECKS[code] for code in sorted(CHECKS)]
