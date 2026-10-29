# Product Requirements Document: Security Healthcheck

**Technical name:** `security_health_checklist`\
**Platform:** Odoo 17.0 Community (CE) and Enterprise (EE)\
**Author:** Arif N Ramadhan\
**Website:** [www.niits.id](https://www.niits.id)\
**Email:** sqlrif@gmail.com\
**License:** OPL-1 (Odoo Proprietary License v1.0)\
**Document version:** 1.0 (Draft)\
**Date:** October 29, 2026

## 1. Document Overview

| Item | Value |
| --- | --- |
| Product name | Security Healthcheck |
| Module technical name | `security_health_checklist` |
| Odoo version | 17.0 |
| Editions | Community and Enterprise |
| Deployment targets | On-premise, Odoo.sh, self-managed cloud/VPS |
| Dependencies | `base`, `mail` only (no third-party dependencies) |
| Category | Administration / Technical |
| Application | Yes (own top-level menu) |

### 1.1 Purpose of this document

This PRD defines the scope, functional and non-functional requirements, data model, scoring logic, user interface, security constraints and acceptance criteria for the Security Healthcheck module. It is the reference for design, development, QA and release.

### 1.2 Glossary

| Term | Meaning |
| --- | --- |
| Scan | One execution of all enabled checks, producing a score, a grade and a list of results |
| Check | A single read-only test of one security or health aspect |
| Finding | The result of a check that is not fully passed (fail or warning) |
| Area | A group of related checks (for example Authentication, Configuration) |
| Score | A number from 0 to 100 representing overall security health |
| Grade | A letter from A (best) to F (worst) derived from the score |

## 2. Background and Problem Statement

Odoo is frequently deployed with risky defaults and left unreviewed after go-live. Typical issues include:

- An open database manager (`list_db` enabled, weak or default master password).
- Administrators without two-factor authentication (2FA).
- Demo data left installed in production databases.
- Weak or missing brute-force protection and weak password policy.
- Forgotten API keys that never expire.
- Custom Python code stored in server actions or automated actions that can be edited from the UI.
- Debug options, test options and insecure transport (HTTP, unencrypted SMTP).

Companies rarely have a quick, understandable way to measure this. Integrators perform manual audits that are costly and inconsistent. Management and hosting providers have no simple artefact to track progress.

## 3. Product Vision and Goals

### 3.1 Vision

Give any Odoo administrator a one-click, safe and understandable security and health assessment of an Odoo instance, with a shareable report that drives concrete remediation.

### 3.2 Goals

1. Provide a **score out of 100**, a **grade from A to F**, a **score per area** and a **trend** over previous scans.
2. Explain every finding in plain language: what was found, why it matters, how to fix it, and a link to the affected records.
3. Be **safe by design**: strictly read-only with respect to the instance, no password guessing, no external calls.
4. Produce a **branded, shareable PDF report** with a summary, top priority actions and a recommendation for every finding.
5. Work identically on CE and EE, on Odoo.sh and on-premise, with no extra dependencies.

### 3.3 Non-Goals

- Automatic remediation or changing any setting (the module only reports).
- Penetration testing, vulnerability exploitation, port scanning or network scanning.
- Password guessing, password cracking or testing of user credentials.
- Calling external services, CVE feeds or telemetry endpoints.
- Operating system, firewall, reverse proxy or PostgreSQL hardening audits beyond what is visible from within the Odoo process.
- Compliance certification (ISO 27001, SOC 2). The report supports but does not replace an audit.

### 3.4 Success Metrics

| Metric | Target |
| --- | --- |
| Full scan duration on a database with 100 users and 50 server actions | Under 15 seconds |
| False positive rate on the reference test instances | Under 5% |
| Findings with explanation, recommendation and affected-record link | 100% where records exist |
| Modules or settings changed by a scan | 0 |
| Outbound network calls during a scan | 0 |

## 4. Target Users and Personas

| Persona | Needs |
| --- | --- |
| **System Administrator / IT Manager** | Run scans, understand findings, fix issues, show progress |
| **Odoo Integrator / Consultant** | Quick audit of a customer instance, a report to attach to a handover or proposal |
| **Hosting Provider / DevOps** | Verify configuration baselines on customer instances |
| **Management / Auditor** | A simple score, trend and PDF without technical detail overload |

Only users with **Settings (Administration)** rights (`base.group_system`) can access the module. Other users see nothing: no menu, no model access, no report.

## 5. Scope

### 5.1 In scope

- Run a healthcheck from the UI and from an optional scheduled action.
- Catalog of read-only checks across six areas (Section 7).
- Scoring, grading, area scores and trend history.
- Finding detail with explanation, impact, recommendation and affected records.
- PDF report (QWeb) printable per scan.
- Scan history with comparison to the previous scan.
- Check configuration: enable or disable a check and mark a finding as an accepted risk.
- Multi-company awareness for company-scoped data.

### 5.2 Out of scope (v1.0)

- Email delivery of the report (user prints or downloads and shares manually).
- Remote or multi-instance dashboard.
- Automated fixes or one-click remediation.
- Custom user-defined checks through the UI (planned for later versions).

### 5.3 Edition support

| Capability | Community | Enterprise |
| --- | --- | --- |
| Run scan, score, grade, history | Yes | Yes |
| PDF report | Yes | Yes |
| 2FA check | Based on `auth_totp` if installed | Based on `auth_totp` if installed |
| Odoo.sh environment detection | N/A | Yes (via environment) |
| Studio-created automations check | N/A | Yes, only if Studio is installed |
| Enterprise license/modules awareness | N/A | Yes, informational |

The module must install and run on both editions with the same code base. EE-only checks must be skipped gracefully (status *Not applicable*) when the required app is absent. No hard dependency on any Enterprise module is allowed.

## 6. Functional Requirements

### 6.1 Run a healthcheck (FR-01)

- **FR-01.1** Menu *Security Healthcheck > Run healthcheck* opens a wizard with a **Run scan** button and a short description of what is checked.
- **FR-01.2** Running a scan creates a `shc.scan` record, executes all enabled checks and stores one `shc.scan.result` per check.
- **FR-01.3** After execution the user is redirected to the scan result form showing score, grade, area scores and findings.
- **FR-01.4** A check that raises an exception must not abort the scan. It is recorded with status *Error* and excluded from scoring, and the error is logged.
- **FR-01.5** A scan must not modify any record outside the module's own models.
- **FR-01.6** The scan runs under the current user and uses `sudo()` strictly for reading data required by the checks.

### 6.2 Score, grade and trend (FR-02)

- **FR-02.1** Each scan has an overall score (0 to 100) and a grade (A to F).
- **FR-02.2** Each area has its own score (0 to 100) and grade.
- **FR-02.3** The History view shows a trend chart (line) of overall score for the last scans (default last 12) and a list with date, score, grade, number of critical, high, medium and low findings, and delta versus the previous scan.
- **FR-02.4** The scoring formula must be documented in the report and deterministic: the same instance state yields the same score.

### 6.3 Findings explained (FR-03)

Every result must contain:

| Field | Description |
| --- | --- |
| Title | Short name of the check |
| Status | Passed, Warning, Failed, Not applicable, Error, Accepted risk |
| Severity | Critical, High, Medium, Low, Info |
| What was found | Plain-language description of the observed state, with numbers when relevant |
| Why it matters | Plain-language explanation of the risk |
| Recommendation | Concrete steps to remediate |
| Affected records | Smart link or button opening the list of affected records (users, server actions, API keys, modules, parameters) |
| Reference | Optional documentation topic name (text only, no external call) |

### 6.4 Accepted risk and check configuration (FR-04)

- **FR-04.1** An administrator can disable a check globally (it is then not executed and not scored).
- **FR-04.2** An administrator can mark a finding as an **accepted risk** with a mandatory justification. Accepted findings are shown separately, excluded from penalty, and listed in the PDF with the justification.
- **FR-04.3** Accepted risks persist across scans (matched by check code and, where relevant, affected record identifier).
- **FR-04.4** Disabling a check or accepting a risk must be visible in the report so the score cannot be misrepresented.

### 6.5 PDF report (FR-05)

- **FR-05.1** A *Print* action on the scan form produces a PDF via QWeb using the company's external layout (logo, name, colors).
- **FR-05.2** Report content, in order:
  1. Cover: company, database name, Odoo version and edition, scan date, generated by.
  2. Executive summary: overall score, grade, area scores, counts by severity, trend versus previous scan.
  3. Top priority actions: up to 10 failed findings ordered by severity then penalty.
  4. Detailed findings: for every non-passed result, the fields in Section 6.3.
  5. Passed checks: a compact list.
  6. Disabled checks and accepted risks with justification.
  7. Methodology and scoring explanation, and a disclaimer.
- **FR-05.3** The report must not include secrets: no password, API key value, token, master password or hash. Only identifiers, names and counts.
- **FR-05.4** The report is generated server-side with no external resources (fonts and images embedded or local).

### 6.6 History (FR-06)

- **FR-06.1** Menu *Security Healthcheck > History* lists all scans with filters (grade, date, user) and group-by (month, grade).
- **FR-06.2** Scans can be opened, printed and deleted by administrators. Optional retention setting: delete scans older than N months (default: keep all).
- **FR-06.3** A *Compare with previous* indicator shows findings newly introduced and findings resolved since the previous scan.

### 6.7 Scheduled scan (FR-07, optional)

- **FR-07.1** A disabled-by-default scheduled action runs a weekly scan.
- **FR-07.2** When enabled, a chatter message is posted on the scan record and a notification is sent to the users selected in settings only if the grade drops or a new Critical finding appears. No external mail is sent unless the user has configured outgoing mail.

## 7. Check Catalog

All checks are read-only. Detection methods use the Odoo ORM, `odoo.tools.config`, `ir.config_parameter` and runtime information available inside the process. Severity values are defaults and are fixed in code in v1.0.

### 7.1 Area: Access and Authentication

| Code | Check | Severity | Detection |
| --- | --- | --- | --- |
| AUTH-01 | Administrators (Settings group) without 2FA | Critical | Users in `base.group_system` where `totp_enabled` is false; N/A if `auth_totp` is not installed |
| AUTH-02 | 2FA module not installed | High | `auth_totp` not in installed modules |
| AUTH-03 | Default administrator login | Medium | Active user with login `admin` and Settings rights |
| AUTH-04 | Too many administrators | Medium | Active users with Settings rights above a threshold (default 3) |
| AUTH-05 | Dormant administrators | Medium | Settings users with no login for more than 90 days (`login_date`) or never logged in |
| AUTH-06 | Password policy too weak | Medium | `auth_password_policy.minlength` below 12 |
| AUTH-07 | Open or loose public sign-up | Medium | `auth_signup.invitation_scope` set to open sign-up for all, or uninvited sign-up allowed |
| AUTH-08 | Generic accounts with high privileges | Low | Active internal users with generic-looking logins (info, admin, test, demo) and elevated groups |
| AUTH-09 | Brute-force protection not detected | High | No known login rate-limiting module installed (configurable list); advisory that limiting should also exist at reverse proxy or fail2ban level |

The module must **never** test any password against any account. Password-related checks inspect policy and configuration only.

### 7.2 Area: Database and Server Configuration

| Code | Check | Severity | Detection |
| --- | --- | --- | --- |
| CFG-01 | Database manager exposed | Critical | `config['list_db']` is true |
| CFG-02 | Master password weak, default or in clear text | Critical | `config['admin_passwd']` equals `admin`, is empty, or is not in hashed (`$pbkdf2-sha512$`) format. The value is never displayed |
| CFG-03 | Database filter not set | High | `config['dbfilter']` empty while multiple databases exist |
| CFG-04 | Debug or verbose logging in production | Medium | `log_level` in debug levels; `dev_mode` active |
| CFG-05 | Test options enabled | Medium | `test_enable` or `test_file` set |
| CFG-06 | Unsafe proxy mode | Medium | `proxy_mode` inconsistent with the presence of forwarded headers |
| CFG-07 | Threaded mode in production | Low | `workers` equals 0 on a non-development instance |
| CFG-08 | Base URL not HTTPS | High | `web.base.url` starts with `http://` and is not localhost |
| CFG-09 | Base URL not frozen | Low | `web.base.url.freeze` not set |
| CFG-10 | Unencrypted outgoing mail | Medium | Active `ir.mail_server` records with `smtp_encryption` equal to `none` |
| CFG-11 | Odoo version support status | High | `odoo.release.version_info` compared with a supported-versions table bundled in the module (no external call) |
| CFG-12 | Python version support status | Low | `sys.version_info` compared with the bundled table |

### 7.3 Area: Data and Demo Content

| Code | Check | Severity | Detection |
| --- | --- | --- | --- |
| DATA-01 | Demo data installed | High | Installed modules with `demo` true; demo users with known demo logins |
| DATA-02 | Public attachments | Medium | `ir.attachment` records with `public` true outside website assets; count and sample |
| DATA-03 | Sensitive models without record rules | Low | Advisory on sensitive models (for example bank accounts, employees when installed) with ACL but no rules |
| DATA-04 | Global ACL entries open to everyone | High | `ir.model.access` with empty group and write, create or unlink permission |

### 7.4 Area: API Keys and Integrations

| Code | Check | Severity | Detection |
| --- | --- | --- | --- |
| API-01 | Old API keys | Medium | `res.users.apikeys` older than 180 days (`create_date`) |
| API-02 | API keys without expiration | Medium | `expiration_date` empty (only when the field exists in the installed build) |
| API-03 | API keys owned by inactive or dormant users | High | Key owner archived or without login for 90 days |
| API-04 | API keys owned by administrators | Medium | Key owner in `base.group_system` |
| API-05 | Active external integration endpoints | Info | Webhook-type automations when available |

Key names, owners and ages are displayed. Key values and hashes are never read into results or the report.

### 7.5 Area: Custom Code and Automation

| Code | Check | Severity | Detection |
| --- | --- | --- | --- |
| CODE-01 | Server actions executing Python code | High | `ir.actions.server` with `state = 'code'` and non-empty code |
| CODE-02 | Automated actions running Python code | High | `base.automation` linked to code server actions (only if `base_automation` is installed) |
| CODE-03 | Code actions modified recently | Medium | Code server actions with `write_date` in the last 30 days |
| CODE-04 | Scheduled actions running as a privileged user | Medium | Active `ir.cron` owned by a Settings user and running code or a server action |
| CODE-05 | Risky code patterns (advisory) | Medium | Pattern scan of server action code for `os.system`, `subprocess`, `eval(`, `exec(`, `__import__`, and `cr.execute` with string formatting. Code is never executed |
| CODE-06 | Custom and third-party modules installed | Info | Installed modules whose author is not Odoo S.A.; count, list and license field |
| CODE-07 | Studio customizations present | Info | EE only: Studio-created automations and views, if `web_studio` is installed |

### 7.6 Area: Platform and Health

| Code | Check | Severity | Detection |
| --- | --- | --- | --- |
| HLT-01 | Modules pending upgrade | Medium | `ir.module.module` in state `to upgrade` or `to install` |
| HLT-02 | Broken module states | Medium | Modules in unexpected states (for example `uninstallable` while expected installed) |
| HLT-03 | Failing scheduled actions | Low | Active `ir.cron` with `failure_count` above zero when available |
| HLT-04 | Failed emails | Low | `mail.mail` in exception state |
| HLT-05 | Attachment storage mode | Info | Database vs filestore, informational |
| HLT-06 | Environment detection | Info | Odoo.sh (via environment variables), on-premise or unknown |

The catalog above is the v1.0 baseline. Each check is an independent Python class in a registry, so new checks can be added without changing the scoring engine.

## 8. Scoring Model

### 8.1 Severity weights

| Severity | Penalty weight (W) |
| --- | --- |
| Critical | 10 |
| High | 6 |
| Medium | 3 |
| Low | 1 |
| Info | 0 |

### 8.2 Result values

| Status | Penalty factor (F) |
| --- | --- |
| Passed | 0 |
| Warning | 0.5 |
| Failed | 1 |
| Not applicable, Error, Disabled, Accepted risk | Excluded from numerator and denominator |

### 8.3 Formulas

- Area score = `100 x (1 - sum(W x F) / sum(W))` over included checks in the area. If an area has no included checks, it is shown as N/A and excluded from the overall score.
- Overall score = weighted average of area scores using area weights.
- Default area weights: Access and Authentication 30, Database and Server Configuration 25, Data and Demo Content 10, API Keys and Integrations 15, Custom Code and Automation 15, Platform and Health 5.
- **Critical cap:** if any Critical finding has status Failed, the overall grade cannot be better than **C**, regardless of numeric score.

### 8.4 Grade bands

| Grade | Score |
| --- | --- |
| A | 90 to 100 |
| B | 80 to 89 |
| C | 70 to 79 |
| D | 60 to 69 |
| E | 50 to 59 |
| F | Below 50 |

## 9. Data Model

Prefix `shc.` is used for all models. All models are restricted to `base.group_system`.

### 9.1 `shc.scan`

| Field | Type | Notes |
| --- | --- | --- |
| name | Char | Sequence, for example SHC/2026/0001 |
| date | Datetime | Scan start |
| duration | Float | Seconds |
| user\_id | Many2one `res.users` | Who ran the scan |
| company\_id | Many2one `res.company` | Default current company |
| odoo\_version | Char | Server version string |
| odoo\_edition | Selection | community, enterprise |
| environment | Selection | onpremise, odoosh, unknown |
| score | Float | 0 to 100 |
| grade | Selection | A to F |
| capped | Boolean | True when the critical cap was applied |
| result\_ids | One2many `shc.scan.result` |  |
| area\_score\_ids | One2many `shc.scan.area` |  |
| count\_critical, count\_high, count\_medium, count\_low | Integer | Computed, stored |
| previous\_scan\_id | Many2one `shc.scan` | For trend and delta |
| state | Selection | running, done, failed |

### 9.2 `shc.scan.area`

| Field | Type |
| --- | --- |
| scan\_id | Many2one `shc.scan` |
| area | Selection (auth, config, data, api, code, health) |
| score | Float |
| grade | Selection |
| weight | Float |

### 9.3 `shc.scan.result`

| Field | Type | Notes |
| --- | --- | --- |
| scan\_id | Many2one `shc.scan` | Ondelete cascade |
| code | Char | For example AUTH-01 |
| area | Selection |  |
| title | Char | Translatable |
| status | Selection | passed, warning, failed, na, error, accepted |
| severity | Selection | critical, high, medium, low, info |
| found | Text | What was found |
| why | Text | Why it matters |
| recommendation | Text | How to fix |
| affected\_model | Char | Technical model name |
| affected\_ids | Char | JSON list of record ids (capped at 500) |
| affected\_count | Integer |  |
| penalty | Float | Computed contribution |

A method `action_open_affected()` returns a window action for the affected model with a domain on the stored ids. Only models accessible to the current user are opened.

### 9.4 `shc.check.config`

| Field | Type | Notes |
| --- | --- | --- |
| code | Char | Unique |
| active | Boolean | Enabled flag |
| note | Text | Optional |

### 9.5 `shc.accepted.risk`

| Field | Type | Notes |
| --- | --- | --- |
| code | Char | Check code |
| res\_key | Char | Optional identifier of the affected record |
| justification | Text | Required |
| user\_id | Many2one `res.users` | Who accepted |
| date | Datetime |  |
| expiry\_date | Date | Optional review date; an expired acceptance counts as not accepted |

## 10. User Interface Requirements

### 10.1 Menu structure

- **Security Healthcheck** (top-level app, Settings group only)
  - **Run healthcheck**
  - **History** (list, form, graph)
  - **Configuration**
    - **Checks** (enable or disable checks)
    - **Accepted risks**
    - **Settings** (thresholds, retention, scheduled scan)

### 10.2 Views

- **Dashboard (scan form):** header with large score, grade badge, area score cards with progress bars, severity counters, and the findings list grouped by area and colored by severity.
- **Finding detail:** a form or dialog with the Section 6.3 fields, an *Open affected records* button and an *Accept risk* button.
- **History:** list, line graph of score over time, and pivot by grade.
- **Filters:** by status, severity and area. The default filter shows only non-passed findings.
- **Language and wording:** plain language, short sentences, no unexplained jargon. All strings are translatable via standard `.po` files. The source language is English.
- **Accessibility:** status conveyed by text and icon as well as color.

## 11. Security Requirements

| ID | Requirement |
| --- | --- |
| SEC-01 | Menus, models, reports and actions are accessible only to `base.group_system`. The ACL file grants no access to other groups |
| SEC-02 | The module changes no setting, user, config parameter or module state. It writes only to `shc.*` models |
| SEC-03 | No password guessing or authentication attempts against user accounts |
| SEC-04 | No external network calls: no HTTP requests, DNS lookups, telemetry or update checks. Supported-versions data is bundled in the module |
| SEC-05 | No secret is stored or displayed: master password, API key values, hashes, session ids, tokens and passwords are excluded from results, logs and the PDF |
| SEC-06 | Server action code is scanned for patterns only and never executed. Code excerpts are limited to the matching line and truncated |
| SEC-07 | `sudo()` is used only for reads required by checks and never to write outside module models |
| SEC-08 | Access to affected records follows the current user's rights; where rights are insufficient the link is hidden |
| SEC-09 | Scan start, finish and duration are logged at INFO level without sensitive content |
| SEC-10 | Multi-company: results that depend on company data respect the allowed companies of the user |
| SEC-11 | The module exposes no HTTP controllers or public endpoints and contains no server actions with Python code, so it passes its own healthcheck |

## 12. Non-Functional Requirements

| ID | Requirement |
| --- | --- |
| NFR-01 | **Performance:** a scan completes in under 15 seconds on reference data; checks use `search_read`, `read_group` and counts instead of loading full recordsets |
| NFR-02 | **Reliability:** failure of one check never aborts the scan; soft timeout per check (default 10 seconds) |
| NFR-03 | **Compatibility:** Odoo 17.0 CE and EE, PostgreSQL 12 and above, Python 3.10 and above, on-premise and Odoo.sh |
| NFR-04 | **Dependencies:** `base` and `mail` only. Optional integrations are detected at runtime and never imported at module load |
| NFR-05 | **Maintainability:** one Python class per check, a shared base class, a check registry, and unit-testable pure functions for scoring |
| NFR-06 | **Localization:** English source strings, translation-ready |
| NFR-07 | **Upgradability:** no monkey patching and no override of core models; compatible with `-u` updates |
| NFR-08 | **Data volume:** result rows per scan are bounded (about 50 to 100); affected ids capped at 500 per result |
| NFR-09 | **Uninstall:** clean uninstall removes all module data without affecting other modules |

## 13. Technical Design

### 13.1 Module structure

```
security_health_checklist/
|-- __init__.py
|-- __manifest__.py
|-- LICENSE
|-- models/
|   |-- shc_scan.py
|   |-- shc_scan_area.py
|   |-- shc_scan_result.py
|   |-- shc_check_config.py
|   |-- shc_accepted_risk.py
|   `-- res_config_settings.py
|-- checks/
|   |-- base_check.py
|   |-- registry.py
|   |-- auth_checks.py
|   |-- config_checks.py
|   |-- data_checks.py
|   |-- api_checks.py
|   |-- code_checks.py
|   `-- health_checks.py
|-- wizard/
|   `-- shc_run_wizard.py
|-- report/
|   |-- shc_report.xml
|   `-- shc_report_templates.xml
|-- views/
|-- security/
|   |-- ir.model.access.csv
|   `-- shc_security.xml
|-- data/
|   |-- shc_sequence.xml
|   |-- shc_cron.xml
|   `-- supported_versions.xml
|-- static/description/   (icon, banner, index.html, screenshots)
|-- i18n/
`-- tests/
```

### 13.2 Manifest (summary)

```python
{
    'name': 'Security Healthcheck',
    'summary': 'Security and health score, grade and PDF report for your Odoo instance',
    'version': '17.0.1.0.0',
    'category': 'Administration',
    'author': 'Arif N Ramadhan',
    'website': 'https://www.niits.id',
    'maintainer': 'Arif N Ramadhan',
    'support': 'sqlrif@gmail.com',
    'license': 'OPL-1',
    'depends': ['base', 'mail'],
    'data': [...],
    'application': True,
    'installable': True,
    'auto_install': False,
    'images': ['static/description/banner.png'],
}
```

### 13.3 Check interface

Every check inherits a base class exposing `code`, `area`, `severity`, `title`, `applicable(env)` and `run(env)`. `run` returns a structure with `status`, `found`, `affected_model` and `affected_ids`. The texts for *why* and *recommendation* are defined in the class and wrapped in translation functions. The runner loads all checks from the registry, skips disabled ones, and wraps each execution in a savepoint and a try/except block.

### 13.4 Compatibility handling

- Fields that vary by version or installed module (`expiration_date`, `totp_enabled`, `failure_count`) are checked with `field in model._fields` before use.
- Models from optional apps (`base.automation`, `web_studio`) are accessed only when present in `env.registry`.
- Odoo.sh detection uses runtime environment information, never network calls.

### 13.5 Report

A QWeb PDF report bound to `shc.scan` and built on `web.external_layout`, so company branding applies automatically in both editions. Styling is inline CSS only; any chart is rendered as inline SVG or CSS bars.

## 14. Edition-Specific Considerations

| Topic | Community | Enterprise |
| --- | --- | --- |
| 2FA | `auth_totp` available and checkable | Same |
| Odoo.sh | Not applicable | Detected. Configuration checks account for platform-managed database manager, proxy and workers; those checks are reported as Passed or Info with a note |
| Studio | Not available | CODE-07 informational check when installed |
| License awareness | Standard modules LGPL-3 | Enterprise modules OEEL-1; shown in CODE-06 as information only, never as a finding |
| Version support | Same bundled table | Same bundled table |

No code path may import Enterprise modules. EE behavior is activated only by runtime detection.

## 15. Licensing and Distribution

- **License:** OPL-1 (Odoo Proprietary License v1.0). The `LICENSE` file with the OPL-1 text is included at the module root and the manifest declares `'license': 'OPL-1'`.
- **Copyright:** Arif N Ramadhan, [www.niits.id](https://www.niits.id), sqlrif@gmail.com.
- **Distribution:** Odoo Apps Store (OPL-1 modules require a price in the manifest) or direct distribution to customers.
- **Source headers:** every Python and XML file carries a short header with the module name, author, website and license.
- **Commercial terms** (per user or per instance) are defined in the customer contract and are out of scope for this document.
- **Third-party code:** none planned. If any is added, its license must be compatible with OPL-1 and documented.

## 16. Testing and Quality

### 16.1 Test strategy

| Level | Scope |
| --- | --- |
| Unit tests | Scoring engine (weights, formulas, cap, grade bands) and each check with controlled fixtures |
| Integration tests (`TransactionCase`) | Full scan, accepted risk behavior, history delta, ACL |
| Security tests | Non-admin user cannot read models, run the wizard or print the report; no writes outside `shc.*`; no network access (patched socket) |
| Report tests | PDF renders without error and contains no secrets |
| Compatibility tests | Odoo 17 CE and EE, with and without optional apps (`auth_totp`, `base_automation`, `web_studio`) |
| Performance tests | Databases with large user and action volumes |

### 16.2 Acceptance criteria

1. Installing on a clean Odoo 17 CE and EE database succeeds with only `base` and `mail` available.
2. A non-administrator cannot see the menu or access any `shc.*` record.
3. A scan on an instance with demo data, default master password and an administrator without 2FA reports at least DATA-01, CFG-02 and AUTH-01 as Failed, and a grade not better than C.
4. A scan on a hardened reference instance yields grade A or B with no Critical findings.
5. After a scan, no record outside `shc.*` has a changed `write_date` attributable to the module.
6. A network trace during a scan shows zero outbound connections.
7. The PDF includes summary, top actions, per-finding recommendations, accepted risks and methodology, and contains no secret values.
8. A second scan after fixing a finding shows an improved score, a positive delta and the finding listed as resolved.
9. A failing check is shown as Error and the scan still completes.
10. Uninstalling the module leaves the database consistent.

## 17. Release Plan

| Milestone | Deliverable |
| --- | --- |
| M1 - Foundation | Manifest, models, ACL, check registry, scoring engine with unit tests |
| M2 - Core checks | Authentication, Configuration and Data checks |
| M3 - Advanced checks | API keys, Custom code, Platform and Health checks |
| M4 - UI | Scan dashboard, finding detail, history, accepted risks, settings |
| M5 - Report | QWeb PDF report and branding |
| M6 - QA and packaging | CE/EE test matrix, translations, app store description, screenshots, OPL-1 license file |
| M7 - Release | Version 17.0.1.0.0 and documentation |

### 17.1 Roadmap after v1.0

- Custom checks defined by the administrator.
- Email delivery of reports and scheduled summaries.
- More checks: website exposure, portal permissions, QWeb template risks.
- Export of results as JSON or XLSX.
- Support for newer Odoo versions.

## 18. Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Config values (for example `list_db`) cannot reflect reverse proxy protection | False positives | Wording states what Odoo sees; accepted-risk feature; note in the recommendation |
| Odoo.sh manages parts of the configuration | Misleading failures | Environment detection and adjusted messages |
| Differences between 17.0 builds | Check errors | Field and model existence guards; per-check error isolation |
| Code pattern scan gives false positives | Noise | Medium severity, labeled advisory, only the matching line shown |
| A high score is read as full security | Over-trust | Disclaimer in UI and report: not an audit and not a guarantee |
| Bundled supported-versions table becomes outdated (no external calls) | Stale advice | Table versioned in a data file, updated each release, date shown in the report |
| Sensitive information leaks through the report | Security incident | Strict redaction rules, no value fields in results, automated secret-leak tests |

## 19. Assumptions and Open Questions

### 19.1 Assumptions

- The target database runs Odoo 17.0 and the user has Settings rights.
- Odoo server configuration values are readable from the running process.
- Some infrastructure aspects (firewall, TLS termination, operating system) cannot be observed from inside Odoo.

### 19.2 Open questions

1. Keep the technical name `security_health_checklist` while the marketing and menu name is *Security Healthcheck*? (Proposed: yes.)
2. Should the Critical grade cap (maximum C) be configurable?
3. Default retention for scan history: keep all, or 24 months?
4. Should scheduled scans notify through chatter only, or also by email when outgoing mail is configured?
5. Should the price and Odoo Apps Store listing be defined before milestone M6?

## 20. Approval

| Role | Name | Date | Signature |
| --- | --- | --- | --- |
| Author / Product Owner | Arif N Ramadhan |  |  |
| Technical Reviewer |  |  |  |
| QA Reviewer |  |  |  |
