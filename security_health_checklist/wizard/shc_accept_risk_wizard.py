# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

from odoo import _, fields, models
from odoo.exceptions import UserError


class ShcAcceptRiskWizard(models.TransientModel):
    _name = 'shc.accept.risk.wizard'
    _description = 'Accept Security Healthcheck Risk'

    result_id = fields.Many2one('shc.scan.result', required=True, ondelete='cascade')
    code = fields.Char(related='result_id.code', readonly=True)
    title = fields.Char(related='result_id.title', readonly=True)
    justification = fields.Text(required=True)
    expiry_date = fields.Date(string='Review date')
    apply_to_check = fields.Boolean(
        string='Accept this check as a whole',
        default=True,
        help='If set, later scans skip the penalty for this check code. '
             'Otherwise the acceptance is tied to the current affected records.',
    )

    def action_confirm(self):
        self.ensure_one()
        if not (self.justification or '').strip():
            raise UserError(_('A justification is required.'))
        res_key = False
        if not self.apply_to_check:
            ids = self.result_id._parsed_ids()
            res_key = str(ids[0]) if ids else False
        self.env['shc.accepted.risk'].create({
            'code': self.result_id.code,
            'res_key': res_key,
            'justification': self.justification,
            'user_id': self.env.user.id,
            'expiry_date': self.expiry_date,
        })
        self.result_id.write({'status': 'accepted', 'penalty': 0.0})
        self.result_id.scan_id._recompute_scores()
        return {'type': 'ir.actions.act_window_close'}
