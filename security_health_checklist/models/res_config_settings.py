# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

from odoo import api, fields, models

from ..checks.helpers import DEFAULT_BRUTEFORCE_MODULES


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    shc_admin_threshold = fields.Integer(
        string='Administrator count threshold',
        config_parameter='shc.admin_threshold',
        default=3,
    )
    shc_dormant_days = fields.Integer(
        string='Dormant administrator days',
        config_parameter='shc.dormant_days',
        default=90,
    )
    shc_api_key_max_age_days = fields.Integer(
        string='API key maximum age (days)',
        config_parameter='shc.api_key_max_age_days',
        default=180,
    )
    shc_retention_months = fields.Integer(
        string='Scan retention (months, 0 = keep all)',
        config_parameter='shc.retention_months',
        default=0,
    )
    shc_bruteforce_modules = fields.Char(
        string='Known brute-force modules',
        config_parameter='shc.bruteforce_modules',
        default=','.join(DEFAULT_BRUTEFORCE_MODULES),
    )
    shc_notify_user_ids = fields.Many2many(
        'res.users',
        string='Notify these users after a scheduled scan',
        relation='shc_res_config_notify_user_rel',
        domain=[('share', '=', False)],
    )

    def set_values(self):
        super().set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            'shc.notify_user_ids',
            ','.join(str(i) for i in self.shc_notify_user_ids.ids),
        )

    @api.model
    def get_values(self):
        res = super().get_values()
        raw = self.env['ir.config_parameter'].sudo().get_param('shc.notify_user_ids', '')
        ids = [int(x) for x in str(raw).split(',') if x.strip().isdigit()]
        res['shc_notify_user_ids'] = [(6, 0, ids)]
        return res
