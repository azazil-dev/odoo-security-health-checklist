# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .shc_scan import AREA_SELECTION


class ShcScanResult(models.Model):
    _name = 'shc.scan.result'
    _description = 'Security Healthcheck Result'
    _order = 'scan_id, area, code'
    _rec_name = 'title'

    scan_id = fields.Many2one('shc.scan', required=True, ondelete='cascade', index=True)
    code = fields.Char(required=True, index=True)
    area = fields.Selection(AREA_SELECTION, required=True)
    title = fields.Char(required=True, translate=True)
    status = fields.Selection(
        [
            ('passed', 'Passed'),
            ('warning', 'Warning'),
            ('failed', 'Failed'),
            ('na', 'Not applicable'),
            ('error', 'Error'),
            ('accepted', 'Accepted risk'),
        ],
        required=True,
        index=True,
    )
    severity = fields.Selection(
        [
            ('critical', 'Critical'),
            ('high', 'High'),
            ('medium', 'Medium'),
            ('low', 'Low'),
            ('info', 'Info'),
        ],
        required=True,
        index=True,
    )
    found = fields.Text(string='What was found')
    why = fields.Text(string='Why it matters')
    recommendation = fields.Text()
    reference = fields.Char()
    affected_model = fields.Char()
    affected_ids = fields.Char(help='JSON list of record ids, capped at 500')
    affected_count = fields.Integer()
    penalty = fields.Float()
    show_affected = fields.Boolean(compute='_compute_show_affected')

    @api.depends('affected_model', 'affected_ids')
    def _compute_show_affected(self):
        for result in self:
            result.show_affected = bool(
                result.affected_model
                and result.affected_model in self.env
                and result._parsed_ids()
                and self.env[result.affected_model].check_access_rights('read', raise_exception=False)
            )

    def _parsed_ids(self):
        self.ensure_one()
        if not self.affected_ids:
            return []
        try:
            data = json.loads(self.affected_ids)
            return [int(i) for i in data][:500]
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

    def action_open_affected(self):
        self.ensure_one()
        if not self.show_affected:
            raise UserError(_('You cannot open the affected records with your current access rights.'))
        ids = self._parsed_ids()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Affected records'),
            'res_model': self.affected_model,
            'view_mode': 'tree,form',
            'domain': [('id', 'in', ids)],
            'target': 'current',
        }

    def action_accept_risk(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Accept risk'),
            'res_model': 'shc.accept.risk.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_result_id': self.id,
                'default_code': self.code,
            },
        }
