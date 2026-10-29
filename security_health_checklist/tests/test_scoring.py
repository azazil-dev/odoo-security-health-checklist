# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.security_health_checklist.checks.scoring import (
    apply_critical_cap,
    compute_area_score,
    compute_overall_score,
    grade_from_score,
    result_penalty,
)


@tagged('post_install', '-at_install')
class TestScoring(TransactionCase):

    def test_grade_bands(self):
        self.assertEqual(grade_from_score(100), 'A')
        self.assertEqual(grade_from_score(90), 'A')
        self.assertEqual(grade_from_score(89), 'B')
        self.assertEqual(grade_from_score(80), 'B')
        self.assertEqual(grade_from_score(79), 'C')
        self.assertEqual(grade_from_score(70), 'C')
        self.assertEqual(grade_from_score(60), 'D')
        self.assertEqual(grade_from_score(50), 'E')
        self.assertEqual(grade_from_score(49), 'F')
        self.assertFalse(grade_from_score(None))

    def test_area_score_all_passed(self):
        results = [
            {'severity': 'high', 'status': 'passed'},
            {'severity': 'medium', 'status': 'passed'},
        ]
        self.assertEqual(compute_area_score(results), 100.0)

    def test_area_score_failed_critical(self):
        results = [
            {'severity': 'critical', 'status': 'failed'},
            {'severity': 'info', 'status': 'passed'},
        ]
        self.assertEqual(compute_area_score(results), 0.0)

    def test_area_score_excludes_na_and_accepted(self):
        results = [
            {'severity': 'high', 'status': 'na'},
            {'severity': 'high', 'status': 'accepted'},
            {'severity': 'medium', 'status': 'passed'},
        ]
        self.assertEqual(compute_area_score(results), 100.0)

    def test_area_score_warning_half_penalty(self):
        results = [{'severity': 'high', 'status': 'warning'}]
        self.assertEqual(compute_area_score(results), 50.0)

    def test_area_na_when_only_info(self):
        results = [{'severity': 'info', 'status': 'passed'}]
        self.assertIsNone(compute_area_score(results))

    def test_overall_weighted_average(self):
        scores = {
            'auth': 100.0,
            'config': 0.0,
            'data': None,
            'api': 100.0,
            'code': 100.0,
            'health': 100.0,
        }
        overall = compute_overall_score(scores)
        self.assertAlmostEqual(overall, (30 * 100 + 25 * 0 + 15 * 100 + 15 * 100 + 5 * 100) / 90.0)

    def test_critical_cap(self):
        grade, capped = apply_critical_cap('A', True)
        self.assertEqual(grade, 'C')
        self.assertTrue(capped)
        grade, capped = apply_critical_cap('D', True)
        self.assertEqual(grade, 'D')
        self.assertFalse(capped)
        grade, capped = apply_critical_cap('A', False)
        self.assertEqual(grade, 'A')
        self.assertFalse(capped)

    def test_penalty(self):
        self.assertEqual(result_penalty('critical', 'failed'), 10.0)
        self.assertEqual(result_penalty('high', 'warning'), 3.0)
        self.assertEqual(result_penalty('medium', 'accepted'), 0.0)

    def test_deterministic(self):
        results = [
            {'severity': 'critical', 'status': 'failed'},
            {'severity': 'low', 'status': 'passed'},
        ]
        first = compute_area_score(results)
        second = compute_area_score(list(reversed(results)))
        self.assertEqual(first, second)
