# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

from odoo import _, api, fields, models


class ShcRunWizard(models.TransientModel):
    _name = 'shc.run.wizard'
    _description = 'Run Security Healthcheck'

    note = fields.Html(readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res['note'] = self._default_note()
        return res

    def _default_note(self):
        return _(
            '<p>This scan is <strong>read-only</strong>. It does not change settings, '
            'users, passwords or modules. It does not guess passwords and it does not '
            'call the internet.</p>'
            '<p>It reviews authentication, server configuration, demo data, API keys, '
            'custom Python automations and basic platform health, then gives a score '
            'from 0 to 100 and a grade from A to F.</p>'
            '<p>The result is not a penetration test and not a certification.</p>'
        )

    def action_run(self):
        scan = self.env['shc.scan'].create({
            'user_id': self.env.user.id,
            'company_id': self.env.company.id,
        })
        scan._run_scan()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Healthcheck'),
            'res_model': 'shc.scan',
            'res_id': scan.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }
