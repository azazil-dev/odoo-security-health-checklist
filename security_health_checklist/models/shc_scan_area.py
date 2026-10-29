# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

from odoo import fields, models

from .shc_scan import AREA_SELECTION, GRADE_SELECTION


class ShcScanArea(models.Model):
    _name = 'shc.scan.area'
    _description = 'Security Healthcheck Area Score'
    _order = 'scan_id, id'

    scan_id = fields.Many2one('shc.scan', required=True, ondelete='cascade', index=True)
    area = fields.Selection(AREA_SELECTION, required=True)
    score = fields.Float()
    grade = fields.Selection(GRADE_SELECTION)
    weight = fields.Float()
    is_na = fields.Boolean(string='N/A')
