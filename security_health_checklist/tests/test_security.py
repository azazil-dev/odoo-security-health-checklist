# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestShcSecurity(TransactionCase):

    def test_non_admin_cannot_read(self):
        user = new_test_user(self.env, login='shc_internal', groups='base.group_user')
        scan = self.env['shc.scan'].create({})
        scan._run_scan()
        with self.assertRaises(AccessError):
            scan.with_user(user).read(['name', 'score'])
        with self.assertRaises(AccessError):
            self.env['shc.run.wizard'].with_user(user).create({})

    def test_scan_does_not_write_core_records(self):
        param = self.env['ir.config_parameter'].sudo().search([('key', '=', 'web.base.url')], limit=1)
        before = param.write_date if param else None
        user_before = self.env.user.write_date
        scan = self.env['shc.scan'].create({})
        scan._run_scan()
        param.invalidate_recordset()
        self.env.user.invalidate_recordset()
        if param and before:
            self.assertEqual(param.write_date, before)
        self.assertEqual(self.env.user.write_date, user_before)
