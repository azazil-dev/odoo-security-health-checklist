# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

from odoo import api, fields, models

from ..checks.registry import iter_check_classes
from .shc_scan import AREA_SELECTION


class ShcCheckConfig(models.Model):
    _name = 'shc.check.config'
    _description = 'Security Healthcheck Check Configuration'
    _order = 'code'

    code = fields.Char(required=True)
    title = fields.Char(readonly=True)
    area = fields.Selection(AREA_SELECTION, readonly=True)
    severity = fields.Selection(
        [
            ('critical', 'Critical'),
            ('high', 'High'),
            ('medium', 'Medium'),
            ('low', 'Low'),
            ('info', 'Info'),
        ],
        readonly=True,
    )
    active = fields.Boolean(default=True)
    note = fields.Text()

    _code_unique = models.Constraint(
        'unique(code)',
        'Check code must be unique.'
    )

    @api.model
    def _sync_from_registry(self):
        existing = {rec.code: rec for rec in self.with_context(active_test=False).search([])}
        for cls in iter_check_classes():
            if cls.code in existing:
                existing[cls.code].write({
                    'title': cls.title,
                    'area': cls.area,
                    'severity': cls.severity,
                })
            else:
                self.create({
                    'code': cls.code,
                    'title': cls.title,
                    'area': cls.area,
                    'severity': cls.severity,
                    'active': True,
                })
