# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo import _


class ShcAcceptedRisk(models.Model):
    _name = 'shc.accepted.risk'
    _description = 'Security Healthcheck Accepted Risk'
    _order = 'date desc, id desc'

    code = fields.Char(required=True, index=True)
    res_key = fields.Char(string='Affected record key')
    justification = fields.Text(required=True)
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, required=True)
    date = fields.Datetime(default=fields.Datetime.now, required=True)
    expiry_date = fields.Date(string='Review date')
    active = fields.Boolean(default=True)

    @api.constrains('justification')
    def _check_justification(self):
        for rec in self:
            if not (rec.justification or '').strip():
                raise ValidationError(_('A justification is required to accept a risk.'))

    @api.model
    def _valid_risks(self):
        today = fields.Date.today()
        return self.search([
            ('active', '=', True),
            '|', ('expiry_date', '=', False), ('expiry_date', '>=', today),
        ])
