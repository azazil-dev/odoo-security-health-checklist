# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.security_health_checklist.checks.registry import CHECKS


@tagged('post_install', '-at_install')
class TestScan(TransactionCase):

    def test_registry_covers_catalog(self):
        expected = {
            'AUTH-01', 'AUTH-02', 'AUTH-03', 'AUTH-04', 'AUTH-05',
            'AUTH-06', 'AUTH-07', 'AUTH-08', 'AUTH-09',
            'CFG-01', 'CFG-02', 'CFG-03', 'CFG-04', 'CFG-05', 'CFG-06',
            'CFG-07', 'CFG-08', 'CFG-09', 'CFG-10', 'CFG-11', 'CFG-12',
            'DATA-01', 'DATA-02', 'DATA-03', 'DATA-04',
            'API-01', 'API-02', 'API-03', 'API-04', 'API-05',
            'CODE-01', 'CODE-02', 'CODE-03', 'CODE-04', 'CODE-05', 'CODE-06', 'CODE-07',
            'HLT-01', 'HLT-02', 'HLT-03', 'HLT-04', 'HLT-05', 'HLT-06',
        }
        self.assertEqual(set(CHECKS), expected)

    def test_full_scan_completes(self):
        scan = self.env['shc.scan'].create({})
        scan._run_scan()
        self.assertEqual(scan.state, 'done')
        self.assertTrue(scan.result_ids)
        self.assertTrue(scan.area_score_ids)
        self.assertIn(scan.grade, ('A', 'B', 'C', 'D', 'E', 'F'))
        self.assertGreaterEqual(scan.score, 0.0)
        self.assertLessEqual(scan.score, 100.0)
        self.assertFalse(scan.result_ids.filtered(lambda r: r.status == 'error'))

    def test_accepted_risk_excluded_from_score(self):
        scan = self.env['shc.scan'].create({})
        scan._run_scan()
        failed = scan.result_ids.filtered(lambda r: r.status == 'failed')
        if not failed:
            self.skipTest('No failed findings on this instance')
        finding = failed[0]
        before = scan.score
        self.env['shc.accepted.risk'].create({
            'code': finding.code,
            'justification': 'Test exception for this instance.',
        })
        scan2 = self.env['shc.scan'].create({})
        scan2._run_scan()
        accepted = scan2.result_ids.filtered(lambda r: r.code == finding.code)
        self.assertEqual(accepted.status, 'accepted')
        self.assertGreaterEqual(scan2.score, before)

    def test_disabled_check_not_executed(self):
        config = self.env['shc.check.config'].search([('code', '=', 'AUTH-04')], limit=1)
        if not config:
            self.env['shc.check.config']._sync_from_registry()
            config = self.env['shc.check.config'].search([('code', '=', 'AUTH-04')], limit=1)
        config.active = False
        scan = self.env['shc.scan'].create({})
        scan._run_scan()
        self.assertFalse(scan.result_ids.filtered(lambda r: r.code == 'AUTH-04'))
        config.active = True

    def test_error_does_not_abort_scan(self):
        from odoo.addons.security_health_checklist.checks.auth_checks import Auth04

        original = Auth04.run

        def boom(self, env):
            raise RuntimeError('intentional')

        Auth04.run = boom
        try:
            scan = self.env['shc.scan'].create({})
            scan._run_scan()
            self.assertEqual(scan.state, 'done')
            err = scan.result_ids.filtered(lambda r: r.code == 'AUTH-04')
            self.assertEqual(err.status, 'error')
        finally:
            Auth04.run = original

    def test_no_secret_in_results(self):
        scan = self.env['shc.scan'].create({})
        scan._run_scan()
        blob = ' '.join((r.found or '') + ' ' + (r.recommendation or '') for r in scan.result_ids)
        self.assertNotIn('$pbkdf2', blob.lower())
        cfg02 = scan.result_ids.filtered(lambda r: r.code == 'CFG-02')
        self.assertTrue(cfg02)
        self.assertNotIn('salimatmin', (cfg02.found or '').lower())
