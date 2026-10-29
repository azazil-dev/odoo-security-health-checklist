# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

"""Pure scoring functions: same inputs always yield the same score and grade."""

SEVERITY_WEIGHTS = {
    'critical': 10.0,
    'high': 6.0,
    'medium': 3.0,
    'low': 1.0,
    'info': 0.0,
}

STATUS_FACTORS = {
    'passed': 0.0,
    'warning': 0.5,
    'failed': 1.0,
}

EXCLUDED_STATUSES = frozenset({'na', 'error', 'accepted', 'disabled'})

AREA_WEIGHTS = {
    'auth': 30.0,
    'config': 25.0,
    'data': 10.0,
    'api': 15.0,
    'code': 15.0,
    'health': 5.0,
}

AREAS = ('auth', 'config', 'data', 'api', 'code', 'health')

SEVERITY_ORDER = {
    'critical': 0,
    'high': 1,
    'medium': 2,
    'low': 3,
    'info': 4,
}

GRADE_RANK = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4, 'F': 5}


def grade_from_score(score):
    if score is None:
        return False
    if score >= 90:
        return 'A'
    if score >= 80:
        return 'B'
    if score >= 70:
        return 'C'
    if score >= 60:
        return 'D'
    if score >= 50:
        return 'E'
    return 'F'


def compute_area_score(results):
    """Return 0-100 or None when the area has no included checks.

    Each item is a mapping with keys ``severity`` and ``status``.
    Area score = 100 * (1 - sum(W * F) / sum(W)).
    """
    numerator = 0.0
    denominator = 0.0
    for result in results:
        if result.get('status') in EXCLUDED_STATUSES:
            continue
        weight = SEVERITY_WEIGHTS.get(result.get('severity'), 0.0)
        factor = STATUS_FACTORS.get(result.get('status'), 0.0)
        denominator += weight
        numerator += weight * factor
    if denominator <= 0:
        return None
    return max(0.0, min(100.0, 100.0 * (1.0 - numerator / denominator)))


def compute_overall_score(area_scores, area_weights=None):
    """Weighted average of area scores. Areas with a None score are excluded."""
    weights = area_weights or AREA_WEIGHTS
    total_weight = 0.0
    accumulated = 0.0
    for area, score in area_scores.items():
        if score is None:
            continue
        weight = weights.get(area, 0.0)
        total_weight += weight
        accumulated += weight * score
    if total_weight <= 0:
        return None
    return max(0.0, min(100.0, accumulated / total_weight))


def apply_critical_cap(grade, has_critical_failed):
    """If any Critical check failed, the grade cannot be better than C."""
    if not has_critical_failed or not grade:
        return grade, False
    if GRADE_RANK.get(grade, 99) < GRADE_RANK['C']:
        return 'C', True
    return grade, False


def result_penalty(severity, status):
    if status in EXCLUDED_STATUSES:
        return 0.0
    return SEVERITY_WEIGHTS.get(severity, 0.0) * STATUS_FACTORS.get(status, 0.0)
