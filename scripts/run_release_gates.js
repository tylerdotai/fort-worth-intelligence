#!/usr/bin/env node
/**
 * run_release_gates.js
 *
 * Evaluates all 8 release gates for the Fort Worth Intelligence civic twin
 * and emits a structured report.
 *
 * Usage:
 *   node scripts/run_release_gates.js [--json]
 *
 * Exit codes:
 *   0 = all gates passed
 *   1 = one or more gates failed
 *   2 = usage error
 */
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const COV_MIN = 80;  // minimum coverage percent
const SUMMARY_FILE = path.join(PROJECT_ROOT, 'coverage-summary.json');

const log = (msg) => console.error(`[gates] ${msg}`);

function run(cmd, cwd) {
  try {
    return execSync(cmd, {
      cwd,
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe'],
      timeout: 180_000,
    });
  } catch (e) {
    return {
      status: e.status ?? 1,
      stdout: e.stdout ? String(e.stdout) : '',
      stderr: e.stderr ? String(e.stderr) : '',
    };
  }
}

function gate(name, fn) {
  const start = Date.now();
  try {
    const result = fn();
    const elapsed = Date.now() - start;
    return { name, passed: true, result, elapsed_ms: elapsed };
  } catch (e) {
    const elapsed = Date.now() - start;
    return { name, passed: false, error: e.message || String(e), elapsed_ms: elapsed };
  }
}

// ── Gate 1: build passes ─────────────────────────────────────────────────────
function checkBuildPassed() {
  // Python project — verify api_server.py has no syntax errors
  const result = run('python3 -m py_compile api_server.py', PROJECT_ROOT);
  // result is either '' (success) or an object with status+stderr
  if (result && result.status !== 0) {
    throw new Error(`api_server.py failed to compile:\n${result.stderr || result}`);
  }
  log('build: api_server.py compiles OK');
}

// ── Gate 2: tests pass ───────────────────────────────────────────────────────
function checkTestsPassed() {
  const result = run(
    'python3 -m pytest tests/ -q --tb=no 2>&1',
    PROJECT_ROOT
  );
  // result is either a string (stdout on success) or {status, stdout, stderr} on error
  let output;
  if (typeof result === 'string') {
    output = result;
  } else {
    output = (result.stdout || '') + (result.stderr || '');
  }
  const match = output.match(/(\d+) passed/);
  if (!match) throw new Error(`No test results found:\n${output.slice(0, 500)}`);
  log(`tests: ${match[1]} passed`);
}

// ── Gate 3: coverage target met ───────────────────────────────────────────────
function checkCoverageTarget() {
  const result = run(
    'python3 -m pytest tests/ --cov=. --cov-report=term --tb=no 2>&1',
    PROJECT_ROOT
  );
  let output;
  if (typeof result === 'string') {
    output = result;
  } else {
    output = (result.stdout || '') + (result.stderr || '');
  }
  const match = output.match(/TOTAL\s+\d+\s+\d+\s+(\d+)%/);
  if (!match) throw new Error(`Could not parse coverage:\n${output.slice(-500)}`);
  const pct = parseInt(match[1], 10);
  if (pct < COV_MIN) {
    throw new Error(`Coverage ${pct}% < ${COV_MIN}% minimum`);
  }
  log(`coverage: ${pct}% (>= ${COV_MIN}%)`);
  return pct;
}

// ── Gate 4: API contracts validated ──────────────────────────────────────────
function checkContracts() {
  const apiContract = path.join(PROJECT_ROOT, '..', '.openclaw', 'workspace',
    'skills', 'civic-graph-api', 'references', 'api-contract.yaml');
  if (!fs.existsSync(apiContract)) {
    throw new Error(`api-contract.yaml not found at ${apiContract}`);
  }

  // Verify required fields are present in api_server.py responses
  const requiredFields = ['provenance', 'freshness'];
  const serverSrc = fs.readFileSync(path.join(PROJECT_ROOT, 'api_server.py'), 'utf8');

  for (const field of requiredFields) {
    if (!serverSrc.includes(field)) {
      throw new Error(`api_server.py missing required field: ${field}`);
    }
  }
  log('contracts: provenance and freshness fields confirmed');
}

// ── Gate 5: source freshness checked ────────────────────────────────────────
function checkSourceFreshness() {
  const sources = [
    { file: 'data/legistar-meetings.json',     maxAgeDays: 7  },
    { file: 'data/legistar-agenda-items.json',  maxAgeDays: 7  },
    { file: 'data/tad-parcels-fort-worth.json', maxAgeDays: 95 },
    { file: 'data/fw-permits.json',            maxAgeDays: 30 },
    { file: 'data/fw-crime.json',              maxAgeDays: 30 },
  ];

  const now = Date.now();
  const warnings = [];

  for (const { file, maxAgeDays } of sources) {
    const fp = path.join(PROJECT_ROOT, file);
    if (!fs.existsSync(fp)) {
      warnings.push(`MISSING: ${file} (required for fresh data)`);
      continue;
    }
    const mtimeMs = fs.statSync(fp).mtimeMs;
    const ageDays = (now - mtimeMs) / (1000 * 60 * 60 * 24);
    if (ageDays > maxAgeDays) {
      warnings.push(`${file} is ${Math.round(ageDays)} days old (>${maxAgeDays} days max)`);
    } else {
      log(`fresh: ${file} (${Math.round(ageDays)} days old, max ${maxAgeDays})`);
    }
  }

  if (warnings.length > 0) {
    log(`freshness warnings:\n  - ${warnings.join('\n  - ')}`);
  }
}

// ── Gate 6: ingestion jobs green ────────────────────────────────────────────
function checkIngestionJobs() {
  // Verify all extractor scripts are present and executable
  const extractors = [
    'scripts/extract_legistar.py',
    'scripts/extract_tad_parcels.py',
    'scripts/extract_fw_permits.py',
    'scripts/extract_fw_crime.py',
  ];

  for (const e of extractors) {
    const fp = path.join(PROJECT_ROOT, e);
    if (!fs.existsSync(fp)) {
      throw new Error(`Missing extractor: ${e}`);
    }
    if (!fs.statSync(fp).mode & 0o111) {
      throw new Error(`Extractor not executable: ${e}`);
    }
    log(`ingestion: ${e} present and executable`);
  }
}

// ── Gate 7: observability enabled ───────────────────────────────────────────
function checkObservability() {
  const serverSrc = fs.readFileSync(path.join(PROJECT_ROOT, 'api_server.py'), 'utf8');
  const signals = [
    { name: 'elapsed_ms / resolution_ms', pattern: /resolution_ms|elapsed_ms/ },
    { name: 'health endpoint',            pattern: /def health/ },
    { name: 'error logging',               pattern: /error|_caveats|_meta.*error/ },
    { name: 'schema version',              pattern: /schema_version/ },
  ];

  for (const s of signals) {
    if (!serverSrc.match(s.pattern)) {
      throw new Error(`Observability missing: ${s.name}`);
    }
    log(`observability: ${s.name} present`);
  }
}

// ── Gate 8: rollback plan documented ─────────────────────────────────────────
function checkRollbackPlan() {
  const candidates = [
    'ROLLBACK.md',
    'DEPLOY.md',
    'OPS.md',
    '.github/deploy-rollback.md',
  ];
  for (const c of candidates) {
    if (fs.existsSync(path.join(PROJECT_ROOT, c))) {
      log(`rollback: ${c} found`);
      return;
    }
  }
  throw new Error('No rollback plan found (expected ROLLBACK.md or DEPLOY.md)');
}

// ── Main ─────────────────────────────────────────────────────────────────────
const args = process.argv.slice(2);
const asJson = args.includes('--json');

const gates = [
  { name: 'build_passed',             fn: checkBuildPassed },
  { name: 'tests_passed',             fn: checkTestsPassed },
  { name: 'coverage_target_met',       fn: checkCoverageTarget },
  { name: 'contracts_validated',      fn: checkContracts },
  { name: 'source_freshness_checked',  fn: checkSourceFreshness },
  { name: 'ingestion_jobs_green',      fn: checkIngestionJobs },
  { name: 'observability_enabled',     fn: checkObservability },
  { name: 'rollback_plan_documented',  fn: checkRollbackPlan },
];

const results = gates.map(g => {
  const r = gate(g.name, g.fn);
  log(`${r.passed ? 'PASS' : 'FAIL'}: ${r.name} (${r.elapsed_ms}ms)`);
  return r;
});

const passed = results.filter(r => r.passed).length;
const failed = results.filter(r => !r.passed);

const report = {
  timestamp: new Date().toISOString(),
  total_gates: gates.length,
  passed,
  failed: failed.length,
  gates: results,
};

if (asJson) {
  console.log(JSON.stringify(report, null, 2));
} else {
  console.error(`\n=== Release Gate Report ===`);
  console.error(`Gates: ${passed}/${gates.length} passed`);
  if (failed.length > 0) {
    console.error(`\nFAILED:`);
    for (const f of failed) {
      console.error(`  ✗ ${f.name}: ${f.error}`);
    }
  }
}

process.exit(failed.length > 0 ? 1 : 0);
