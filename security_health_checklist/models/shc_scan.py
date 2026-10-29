# -*- coding: utf-8 -*-
# Copyright (C) 2026 Arif N Ramadhan (https://www.niits.id)
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file.

import json
import logging
import time
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo import release
from ..checks.helpers import detect_edition, detect_environment, get_param, get_param_int
from ..checks.registry import iter_check_classes
from ..checks.scoring import (
    AREA_WEIGHTS,
    AREAS,
    SEVERITY_ORDER,
    apply_critical_cap,
    compute_area_score,
    compute_overall_score,
    grade_from_score,
    result_penalty,
)

_logger = logging.getLogger(__name__)

AREA_SELECTION = [
    ('auth', 'Access and Authentication'),
    ('config', 'Database and Server Configuration'),
    ('data', 'Data and Demo Content'),
    ('api', 'API Keys and Integrations'),
    ('code', 'Custom Code and Automation'),
    ('health', 'Platform and Health'),
]

GRADE_SELECTION = [
    ('A', 'A'),
    ('B', 'B'),
    ('C', 'C'),
    ('D', 'D'),
    ('E', 'E'),
    ('F', 'F'),
]


class ShcScan(models.Model):
    _name = 'shc.scan'
    _description = 'Security Healthcheck Scan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(required=True, copy=False, default='New', tracking=True)
    date = fields.Datetime(string='Started on', default=fields.Datetime.now, required=True, index=True)
    duration = fields.Float(string='Duration (s)', readonly=True)
    user_id = fields.Many2one('res.users', string='Run by', default=lambda self: self.env.user, required=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    odoo_version = fields.Char(readonly=True)
    odoo_edition = fields.Selection(
        [('community', 'Community'), ('enterprise', 'Enterprise')],
        readonly=True,
    )
    environment = fields.Selection(
        [('onpremise', 'On-premise'), ('odoosh', 'Odoo.sh'), ('unknown', 'Unknown')],
        readonly=True,
    )
    score = fields.Float(readonly=True, tracking=True)
    grade = fields.Selection(GRADE_SELECTION, readonly=True, tracking=True)
    capped = fields.Boolean(
        string='Critical cap applied',
        help='True when a failed Critical finding forced the grade to C or worse.',
        readonly=True,
    )
    result_ids = fields.One2many('shc.scan.result', 'scan_id', string='Results')
    area_score_ids = fields.One2many('shc.scan.area', 'scan_id', string='Area scores')
    finding_ids = fields.Many2many(
        'shc.scan.result',
        compute='_compute_finding_ids',
        string='Findings',
    )
    count_critical = fields.Integer(compute='_compute_counts', store=True)
    count_high = fields.Integer(compute='_compute_counts', store=True)
    count_medium = fields.Integer(compute='_compute_counts', store=True)
    count_low = fields.Integer(compute='_compute_counts', store=True)
    previous_scan_id = fields.Many2one('shc.scan', readonly=True, ondelete='set null')
    score_delta = fields.Float(compute='_compute_delta', store=True)
    new_finding_codes = fields.Char(compute='_compute_comparison', store=True)
    resolved_finding_codes = fields.Char(compute='_compute_comparison', store=True)
    state = fields.Selection(
        [('running', 'Running'), ('done', 'Done'), ('failed', 'Failed')],
        default='running',
        required=True,
        tracking=True,
    )
    methodology_note = fields.Html(compute='_compute_methodology', sanitize=False)

    @api.depends('result_ids.status', 'result_ids.severity')
    def _compute_counts(self):
        for scan in self:
            findings = scan.result_ids.filtered(lambda r: r.status in ('failed', 'warning'))
            scan.count_critical = len(findings.filtered(lambda r: r.severity == 'critical'))
            scan.count_high = len(findings.filtered(lambda r: r.severity == 'high'))
            scan.count_medium = len(findings.filtered(lambda r: r.severity == 'medium'))
            scan.count_low = len(findings.filtered(lambda r: r.severity == 'low'))

    @api.depends('result_ids.status')
    def _compute_finding_ids(self):
        for scan in self:
            scan.finding_ids = scan.result_ids.filtered(
                lambda r: r.status in ('failed', 'warning', 'error', 'accepted')
            )

    @api.depends('score', 'previous_scan_id.score')
    def _compute_delta(self):
        for scan in self:
            if scan.previous_scan_id:
                scan.score_delta = scan.score - scan.previous_scan_id.score
            else:
                scan.score_delta = 0.0

    @api.depends('result_ids.status', 'result_ids.code', 'previous_scan_id.result_ids.status', 'previous_scan_id.result_ids.code')
    def _compute_comparison(self):
        for scan in self:
            if not scan.previous_scan_id:
                scan.new_finding_codes = False
                scan.resolved_finding_codes = False
                continue
            now = set(scan.result_ids.filtered(lambda r: r.status in ('failed', 'warning')).mapped('code'))
            old = set(scan.previous_scan_id.result_ids.filtered(
                lambda r: r.status in ('failed', 'warning')
            ).mapped('code'))
            scan.new_finding_codes = ', '.join(sorted(now - old)) or False
            scan.resolved_finding_codes = ', '.join(sorted(old - now)) or False

    def _compute_methodology(self):
        for scan in self:
            scan.methodology_note = _(
                '<p>Score = weighted average of area scores. An area score is '
                '100 × (1 − sum(severity weight × status factor) / sum(weights)) '
                'over included checks. Passed = 0, Warning = 0.5, Failed = 1. '
                'Not applicable, Error, Disabled and Accepted risk are excluded. '
                'Weights: Critical 10, High 6, Medium 3, Low 1, Info 0. '
                'Area weights: Authentication 30, Configuration 25, Data 10, '
                'API 15, Code 15, Health 5. If any Critical check failed, the '
                'grade cannot be better than C.</p>'
                '<p>This report is not a penetration test, not a certification, '
                'and not a guarantee. It only reflects what this Odoo process can see.</p>'
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('shc.scan') or 'SHC'
            vals.setdefault('odoo_version', release.version)
            vals.setdefault('odoo_edition', detect_edition(self.env))
            vals.setdefault('environment', detect_environment())
        return super().create(vals_list)

    def action_run(self):
        self.ensure_one()
        self._run_scan()
        return True

    def action_print(self):
        self.ensure_one()
        return self.env.ref('security_health_checklist.action_report_shc_scan').report_action(self)

    def action_open_affected_area(self):
        self.ensure_one()
        return True

    def _previous_done_scan(self):
        return self.search([
            ('state', '=', 'done'),
            ('id', '!=', self.id),
            ('date', '<=', self.date or fields.Datetime.now()),
        ], order='date desc, id desc', limit=1)

    def _run_scan(self):
        self.ensure_one()
        started = time.monotonic()
        _logger.info('SHC scan %s started by %s', self.name, self.env.user.login)
        self.write({
            'state': 'running',
            'odoo_version': release.version,
            'odoo_edition': detect_edition(self.env),
            'environment': detect_environment(),
            'user_id': self.env.user.id,
        })
        self.result_ids.unlink()
        self.area_score_ids.unlink()
        self.env['shc.check.config']._sync_from_registry()
        disabled = set(self.env['shc.check.config'].search([('active', '=', False)]).mapped('code'))
        try:
            for cls in iter_check_classes():
                check = cls()
                if check.code in disabled:
                    continue
                self._run_one_check(check)
            self._apply_accepted_risks()
            self._recompute_scores()
            duration = time.monotonic() - started
            previous = self._previous_done_scan()
            self.write({
                'state': 'done',
                'duration': duration,
                'previous_scan_id': previous.id if previous else False,
            })
            _logger.info(
                'SHC scan %s finished in %.2fs score=%s grade=%s',
                self.name, duration, self.score, self.grade,
            )
            self._apply_retention()
        except Exception:
            duration = time.monotonic() - started
            _logger.exception('SHC scan %s failed after %.2fs', self.name, duration)
            self.write({'state': 'failed', 'duration': duration})
            raise

    def _run_one_check(self, check):
        started = time.monotonic()
        status = 'error'
        found = ''
        affected_model = False
        affected_ids = []
        why = check.why
        recommendation = check.recommendation
        try:
            with self.env.cr.savepoint():
                if not check.applicable(self.env):
                    outcome = check.na(_('Not applicable on this instance (required app or field is missing).'))
                else:
                    outcome = check.run(self.env) or {}
                status = outcome.get('status') or 'error'
                found = outcome.get('found') or ''
                affected_model = outcome.get('affected_model') or False
                affected_ids = list(outcome.get('affected_ids') or [])[:500]
                why = outcome.get('why') or why
                recommendation = outcome.get('recommendation') or recommendation
        except Exception as exc:
            _logger.exception('SHC check %s raised', check.code)
            status = 'error'
            found = _('The check failed with an internal error (%s). The rest of the scan continued.') % type(exc).__name__
        elapsed = time.monotonic() - started
        if elapsed > 10:
            _logger.warning('SHC check %s took %.2fs (soft timeout is 10s)', check.code, elapsed)
        self.env['shc.scan.result'].create({
            'scan_id': self.id,
            'code': check.code,
            'area': check.area,
            'title': check.title,
            'status': status,
            'severity': check.severity,
            'found': found,
            'why': why,
            'recommendation': recommendation,
            'reference': check.reference,
            'affected_model': affected_model or False,
            'affected_ids': json.dumps(affected_ids),
            'affected_count': len(affected_ids),
            'penalty': result_penalty(check.severity, status),
        })

    def _apply_accepted_risks(self):
        risks = self.env['shc.accepted.risk']._valid_risks()
        if not risks:
            return
        for result in self.result_ids:
            if result.status in ('na', 'error', 'passed'):
                continue
            matching = risks.filtered(lambda r: r.code == result.code)
            if not matching:
                continue
            ids = set(str(i) for i in result._parsed_ids())
            if matching.filtered(lambda r: not r.res_key) or matching.filtered(lambda r: r.res_key in ids):
                result.write({
                    'status': 'accepted',
                    'penalty': 0.0,
                })

    def _recompute_scores(self):
        self.ensure_one()
        self.area_score_ids.unlink()
        payloads = [{
            'area': r.area,
            'severity': r.severity,
            'status': r.status,
        } for r in self.result_ids]
        area_scores = {}
        for area in AREAS:
            score = compute_area_score([p for p in payloads if p['area'] == area])
            area_scores[area] = score
            grade = grade_from_score(score) if score is not None else False
            self.env['shc.scan.area'].create({
                'scan_id': self.id,
                'area': area,
                'score': score if score is not None else 0.0,
                'grade': grade,
                'weight': AREA_WEIGHTS.get(area, 0.0),
                'is_na': score is None,
            })
        overall = compute_overall_score(area_scores)
        grade = grade_from_score(overall) if overall is not None else False
        has_critical = bool(self.result_ids.filtered(
            lambda r: r.severity == 'critical' and r.status == 'failed'
        ))
        grade, capped = apply_critical_cap(grade, has_critical)
        for result in self.result_ids:
            result.penalty = result_penalty(result.severity, result.status)
        self.write({
            'score': overall if overall is not None else 0.0,
            'grade': grade,
            'capped': capped,
        })

    def _apply_retention(self):
        months = get_param_int(self.env, 'shc.retention_months', 0)
        if months <= 0:
            return
        cutoff = fields.Datetime.now() - relativedelta(months=months)
        old = self.search([('date', '<', cutoff), ('id', '!=', self.id)])
        if old:
            _logger.info('SHC retention: deleting %s scans older than %s months', len(old), months)
            old.unlink()

    def get_top_actions(self, limit=10):
        self.ensure_one()
        findings = self.result_ids.filtered(lambda r: r.status == 'failed')
        return findings.sorted(
            key=lambda r: (SEVERITY_ORDER.get(r.severity, 9), -(r.penalty or 0.0), r.code)
        )[:limit]

    def get_non_passed_results(self):
        self.ensure_one()
        return self.result_ids.filtered(lambda r: r.status not in ('passed', 'na')).sorted(
            key=lambda r: (SEVERITY_ORDER.get(r.severity, 9), r.code)
        )

    def get_passed_results(self):
        self.ensure_one()
        return self.result_ids.filtered(lambda r: r.status == 'passed')

    def get_disabled_checks(self):
        return self.env['shc.check.config'].search([('active', '=', False)])

    def get_accepted_risks(self):
        return self.env['shc.accepted.risk']._valid_risks()

    def _notify_if_needed(self, previous):
        self.ensure_one()
        raw = get_param(self.env, 'shc.notify_user_ids', '')
        ids = [int(x) for x in str(raw).split(',') if x.strip().isdigit()]
        partners = self.env['res.users'].browse(ids).mapped('partner_id')
        if not partners:
            return
        grade_dropped = bool(
            previous and previous.grade and self.grade
            and self.grade > previous.grade
        )
        prev_crit = set()
        if previous:
            prev_crit = set(previous.result_ids.filtered(
                lambda r: r.severity == 'critical' and r.status == 'failed'
            ).mapped('code'))
        now_crit = set(self.result_ids.filtered(
            lambda r: r.severity == 'critical' and r.status == 'failed'
        ).mapped('code'))
        new_critical_codes = now_crit - prev_crit
        if not grade_dropped and not new_critical_codes:
            return
        body = _(
            'Scheduled healthcheck %s finished with grade %s (score %s).'
        ) % (self.name, self.grade, '%.1f' % self.score)
        if grade_dropped:
            body += _(' Grade dropped from %s.') % previous.grade
        if new_critical_codes:
            body += _(' New critical findings: %s.') % ', '.join(sorted(new_critical_codes))
        self.message_post(body=body, partner_ids=partners.ids, subtype_xmlid='mail.mt_note')

    @api.model
    def _cron_run_scan(self):
        scan = self.create({
            'user_id': self.env.user.id,
            'company_id': self.env.company.id,
        })
        previous = scan._previous_done_scan()
        scan._run_scan()
        scan._notify_if_needed(previous)
        return True
