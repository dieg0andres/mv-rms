// Independent development smoke. Explicit --run only; no installs or cleanup.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { stagingTarget, sameOriginRequest } from './staging-origin.mjs';

export const CANDIDATE = '529e6382e0fc1ca212b20f2400bb83e9de7b5efc';
export const TREE = '5b98b0b2e7de1cd27009b754089f801c770eb745';
export const ORIGIN_SHA = '180c15a36c1ad001f27b7f6b4ebd6d397283344936a45ff64bd5260165aa6bf0';
export const SEED = 'HYP-da014a8c-998c-48d8-872a-de15b5262cb3';
export const OWNED = Object.freeze({ id: 'HYP-8df724d5-53a9-4a62-9cce-839b03ab91bd', version_id: 'HYPV-2ce72c93-f095-4a69-b515-dfc0e8b3de1a', title: 'BROWSER-1c17699a-c11b-4ceb-bcb8-c7a8d68d0bd3 incomplete keyboard' });
export const MARKER = '<img src=x onerror=alert(1)>';
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const sha = value => createHash('sha256').update(value).digest('hex');
const control = (page, name) => page.locator(`form[data-record-form] [name="${name}"]`);

export function config(argv, env) {
  assert.equal(argv.length, 5, 'explicit_run_arguments');
  assert.equal(argv[0], '--run', 'explicit_run_required');
  assert.equal(argv[1], '--run-id', 'run_id_required');
  assert.match(argv[2], uuid, 'unique_run_uuid_required');
  assert.equal(argv[3], '--output', 'output_required');
  assert(path.isAbsolute(argv[4]), 'absolute_output_required');
  stagingTarget(env.RMS_STAGING_ORIGIN); // Before secret access, module load or transport.
  assert.equal(sha(env.RMS_STAGING_ORIGIN), ORIGIN_SHA, 'installed_origin_mismatch');
  assert(path.isAbsolute(env.RMS_PLAYWRIGHT_PACKAGE_ROOT || ''), 'existing_package_root_required');
  return { origin: env.RMS_STAGING_ORIGIN, runId: argv[2], output: argv[4], packageRoot: env.RMS_PLAYWRIGHT_PACKAGE_ROOT };
}

export function fullFields(prefix) {
  return {
    title: `${prefix} complete ${MARKER}`, claim: `${prefix} fictional gross return above matched cash; ${MARKER}`,
    claim_basis: 'gross_return', economic_rationale: 'Invented temporary selling pressure; no finding.',
    expected_opportunity: 'Fictional reversal; costs may erase it.', persistence_argument: 'Episodic liquidity needs may recur.',
    competing_explanations: 'Market rebound, risk and invented fixture construction.',
    falsification_condition: 'A valid later test without predicted advantage would undermine the claim; missing data is inconclusive.',
    market: 'etfs', universe: 'Fixed fictional SYNTH-A and SYNTH-B, selected before the fictional window.', direction: 'long',
    signal: `${prefix} SIGNAL: prior fictional close return at or below -2%.`,
    information_availability: 'Fictional close plus five-minute availability delay; no data used.',
    decision_schedule: `${prefix} DECISION: five minutes after each fictional UTC close.`,
    entry_conditions: `${prefix} ENTRY: enter only while flat; alphabetic tie break; ignore repeat signals while invested.`,
    execution_timing: `${prefix} EXECUTION: next fictional open after information delay; fills await a Test Plan.`,
    exit_conditions: `${prefix} EXIT: close at fictional entry-session close; no stop or target.`,
    exit_precedence: `${prefix} PRECEDENCE: scheduled exit before holding limit; intrabar ordering remains unknown.`,
    effect_horizon: { kind: 'fixed', quantity: '0.125', unit: 'hours', start_anchor: 'Fictional publication', counting_convention: 'Elapsed UTC hours' },
    maximum_holding_period: { kind: 'fixed', quantity: '2', unit: 'bars', start_anchor: 'Intended entry', counting_convention: 'Entry bar counts as one', bar_definition: 'Invented five-minute UTC bars, 09:00 through 09:10; no market calendar claim.' },
    sizing_method: 'equity_fraction', sizing_basis: '10% of fictional pre-entry USD equity.',
    sizing_rule: 'Round down to whole units using pre-submission price; no additions.', exposure_limits: 'One position, at most 10% gross; no borrowing.',
    implementation_assumptions: 'No final fee, slippage, liquidity, fill or settlement model.',
    intended_benchmark_name: `${prefix} intended cash comparison`,
    intended_benchmark_definition: 'Fictional zero-yield USD cash over exactly matching observation windows, no rebalancing.',
    intended_benchmark_rationale: 'Compares entry with staying in cash; does not control beta.',
    research_limitations: 'Invented software fixture only; no empirical result, qualification, Test Plan or trading authority.'
  };
}

export function flatten(value, prefix = '') {
  return Object.fromEntries(Object.entries(value).flatMap(([key, item]) =>
    item && typeof item === 'object' ? Object.entries(flatten(item, `${prefix}/${key}`)) : [[`${prefix}/${key}`, item == null ? '' : String(item)]]));
}

// Derived review notices may legitimately grow during other users' work; immutable
// snapshots and exact context never may. This projection does not compare counts.
export function immutable(record) {
  const { upstream_notices, impact_status, links, ...rest } = record;
  return rest;
}

export function checkSaved(record, expected, version, pins, previous = null) {
  assert.equal(record.version, version, 'exact_version');
  assert.equal(record.status, 'draft', 'draft_stays_draft');
  assert.equal(record.classification, 'synthetic', 'synthetic_stays_synthetic');
  const actual = record.fields;
  for (const [pointer, value] of Object.entries(flatten(expected))) {
    const keys = pointer.split('/').slice(1);
    assert.equal(keys.reduce((v, key) => v?.[key], actual), value, `roundtrip:${pointer}`);
  }
  // Require absent conditional duration values to remain null/absent.
  for (const name of ['effect_horizon', 'maximum_holding_period']) {
    if (expected[name]) for (const [key, value] of Object.entries(actual[name]))
      if (!(key in expected[name])) assert(value == null, `no_duration_default:${name}/${key}`);
  }
  assert.equal(record.origin.idea.version_id, pins.idea, 'exact_idea_pin');
  assert.equal(record.research_context.investigation.version_id, pins.case, 'exact_case_pin');
  assert.equal(record.research_context.idea_family_association.version_id, pins.binding, 'exact_classification_pin');
  if (previous) {
    assert.equal(record.hypothesis_id, previous.hypothesis_id, 'stable_hypothesis');
    assert.equal(record.supersedes_version_id, previous.version_id, 'exact_predecessor');
    assert.equal(record.corrects_version, previous.version, 'reasoned_correction');
    assert.equal(record.origin.association.stable_id, previous.origin.association.stable_id, 'stable_origin_edge');
    assert.equal(record.research_context.hypothesis_investigation_association.stable_id, previous.research_context.hypothesis_investigation_association.stable_id, 'stable_case_edge');
  }
}

export function checkPreserved(before, after) {
  assert.deepEqual(after, before, 'owned_input_and_key_preserved');
}

// Continuation has no create operation except its single missing-reference denial.
export function allowedPost(url, origin, recordId, count, allowMissingCreate = false) {
  if (!sameOriginRequest(url, origin) || count >= 4 || recordId !== OWNED.id) return false;
  const u = new URL(url);
  if (u.search) return false;
  return u.pathname === `/hypotheses/${OWNED.id}/revise` ||
    (allowMissingCreate && u.pathname === '/hypotheses/new');
}

export function savedDestination(raw, origin, location) {
  if (!/^\/hypotheses\/HYP-[0-9a-f-]{36}\/versions\/[1-3]$/.test(location || '') ||
      !sameOriginRequest(String(raw), origin)) return false;
  const u = new URL(String(raw));
  return u.pathname === location && !u.search &&
    (!u.hash || ['#hypothesis-fields', '#research-context'].includes(u.hash));
}

export function safeLocal(raw, origin) {
  let u;
  try {
    u = new URL(String(raw));
    if (!sameOriginRequest(u.href, origin)) throw new Error('other_origin');
  } catch {
    return { current_local_url: '[other-or-no-origin]', origin_equals_expected: false };
  }
  const permitted = /^\/(?:api\/v1\/)?(?:hypotheses|ideas)(?:\/(?:HYP|IDE)-[0-9a-f-]{36}(?:\/(?:versions\/[1-3]|history|revise))?|\/new)?$/.test(u.pathname) ||
    ['/', '/__staging/version', '/research-context'].includes(u.pathname);
  const fragment = !u.hash ? '' : ['#hypothesis-fields', '#research-context', '#draft-errors'].includes(u.hash) ? u.hash : '#redacted';
  return { current_local_url: permitted ? u.pathname + fragment : '[redacted-local-path]', origin_equals_expected: true };
}

export function networkCategory(text) {
  if (String(text).includes('ERR_ABORTED')) return 'ABORTED';
  if (String(text).includes('ERR_NAME_NOT_RESOLVED')) return 'DNS';
  if (/ERR_(CERT|SSL)/.test(String(text))) return 'TLS';
  if (/ERR_(CONNECTION|TIMED_OUT)/.test(String(text))) return 'CONNECTION';
  return 'OTHER_NETWORK';
}

export function assertOwnedBaseline(first, latest, history) {
  assert.equal(first.hypothesis_id, OWNED.id, 'bound_owned_identity');
  assert.equal(first.version_id, OWNED.version_id, 'bound_owned_version');
  assert.equal(first.version, 1, 'bound_owned_v1');
  assert.equal(first.fields.title, OWNED.title, 'bound_original_title');
  assert.equal(first.classification, 'synthetic', 'bound_synthetic');
  assert.deepEqual(immutable(latest), immutable(first), 'owned_still_at_v1_before_writes');
  assert.deepEqual(history.results.map(r => r.version_id), [OWNED.version_id], 'only_owned_v1_before_writes');
}

export async function run(c) {
  // Fail closed if result destination already exists. No retry or cleanup.
  await fs.mkdir(c.output, { recursive: false, mode: 0o700 });
  const result = {
    candidate: CANDIDATE, tree: TREE, origin_sha256: sha(c.origin), run_id: c.runId,
    started_at: new Date().toISOString(), node: process.version,
    result: 'INCONCLUSIVE', assertions: [], requests: [], screenshots: [], committed: [], preservation: [], diagnostics: [], accepted_redirects: [], request_failures: [],
    continuation_of: '1c17699a-c11b-4ceb-bcb8-c7a8d68d0bd3', preexisting_record: OWNED,
    viewer_checks: 'WAIVED BY FOUNDER / NOT EXECUTED', full_H01_H20: 'INCOMPLETE',
    limitations: ['Focused editor browser smoke only', 'No ordinary SQL-role H14 proof', 'No DB transaction-overlap claim', 'No merge, Stage 1 or Risk acceptance']
  };
  let browser, step = 'runtime', recordId = OWNED.id, postCount = 0, unsafe = 0, allowMissingCreate = false, currentPage = null, phase = 'runtime';
  const checkpoint = (label, p = currentPage) => { phase = label; currentPage = p; if (result.diagnostics.length < 200) result.diagnostics.push({ step, phase, ...safeLocal(p?.url() || '', c.origin) }); };
  const pass = name => result.assertions.push({ name, result: 'PASS' });
  const check = (name, action) => { action(); pass(name); };
  try {
    result.checker_sha256 = sha(await fs.readFile(fileURLToPath(import.meta.url)));
    const require = createRequire(path.join(c.packageRoot, 'package.json'));
    assert.equal(require('playwright/package.json').version, '1.56.1', 'reviewed_playwright_version');
    result.playwright = '1.56.1';
    const { chromium } = require('playwright');
    const password = (await fs.readFile('/run/secrets/test_editor_password', 'utf8')).trimEnd();
    assert(password.length > 0, 'existing_editor_secret_empty');
    browser = await chromium.launch({ headless: true });
    result.browser = browser.version();
    const context = await browser.newContext({ httpCredentials: { username: 'test_editor', password }, viewport: { width: 1280, height: 800 }, serviceWorkers: 'block' });
    context.setDefaultTimeout(15000);
    context.setDefaultNavigationTimeout(20000);
    await context.route('**/*', async route => {
      const request = route.request();
      if (!sameOriginRequest(request.url(), c.origin) ||
          (request.method() !== 'GET' && request.method() !== 'HEAD' &&
           (request.method() !== 'POST' || !allowedPost(request.url(), c.origin, recordId, postCount, allowMissingCreate)))) {
        unsafe += 1;
        await route.abort();
      } else {
        if (request.method() === 'POST') postCount += 1;
        await route.continue();
      }
    });
    context.on('requestfailed', r => { if (result.request_failures.length < 20) result.request_failures.push({ ...safeLocal(r.url(), c.origin), category: networkCategory(r.failure()?.errorText || '') }); });
    context.on('page', p => p.on('dialog', async dialog => { unsafe += 1; await dialog.dismiss(); }));
    const page = await context.newPage();
    const local = raw => {
      assert(sameOriginRequest(raw, c.origin), 'same_origin_response');
      const u = new URL(raw); return u.pathname; // Never record private origin or query.
    };
    const api = async route => {
      checkpoint('api_read:' + route);
      assert(route.startsWith('/') && !route.startsWith('//'), 'local_api_path');
      const r = await context.request.get(c.origin + route, { maxRedirects: 0, timeout: 20000 });
      const bytes = await r.body();
      result.requests.push({ method: 'GET', path: route, status: r.status(), body_sha256: sha(bytes) });
      assert.equal(r.status(), 200, 'authorized_api_read');
      return JSON.parse(bytes.toString('utf8'));
    };
    const navigate = async (p, route) => {
      checkpoint('navigate', p);
      const r = await p.goto(c.origin + route, { waitUntil: 'domcontentloaded' });
      assert.equal(r.status(), 200, 'page_status'); assert.equal(local(p.url()), route, 'page_destination');
    };
    const click = async (p, locator) => {
      checkpoint('click_link', p);
      const href = await locator.getAttribute('href');
      const destination = new URL(href, p.url());
      assert(sameOriginRequest(destination.href, c.origin), 'same_origin_link');
      await Promise.all([p.waitForURL(destination.href, { waitUntil: 'domcontentloaded' }), locator.click()]);
    };
    const fill = async (p, name, value) => {
      checkpoint('fill:' + name, p);
      const el = control(p, name); assert.equal(await el.count(), 1, 'implemented_control');
      if (await el.evaluate(e => e.tagName) === 'SELECT') await el.selectOption(value);
      else await el.fill(value);
    };
    const snapshot = p => p.locator('form[data-record-form]').evaluate(form =>
      Object.fromEntries([...new FormData(form)].filter(([key]) => key.startsWith('/') || key === 'idempotency_key')));
    const preserved = async (p, before, name, continueAfterKnownDenial = false) => {
      const after = await snapshot(p);
      const changed = [...new Set([...Object.keys(before), ...Object.keys(after)])].filter(key => before[key] !== after[key]);
      result.preservation.push({ name, changed_paths: changed, before_sha256: sha(JSON.stringify(before)), after_sha256: sha(JSON.stringify(after)) });
      try { checkPreserved(before, after); pass(name); }
      catch (error) {
        result.assertions.push({ name, result: 'FAIL', changed_paths: changed });
        if (!continueAfterKnownDenial) throw error;
        // A confirmed 409 allows the independent read/error slices to continue.
        // Preserve the failure and never retry or submit this losing form again.
      }
    };
    const post = async (p, expectedStatus) => {
      checkpoint('native_submit', p);
      const [r] = await Promise.all([
        p.waitForResponse(r => r.request().method() === 'POST' && sameOriginRequest(r.url(), c.origin)),
        p.locator('button[name="operation"][value="save"]').click(),
      ]);
      checkpoint('native_status', p);
      const requestEvidence = { method: 'POST', path: local(r.url()), status: r.status() };
      result.requests.push(requestEvidence);
      assert.equal(r.status(), expectedStatus, 'native_post_status');
      if (expectedStatus === 303) {
        const location = await r.headerValue('location');
        assert.match(location || '', /^\/hypotheses\/HYP-[0-9a-f-]{36}\/versions\/[23]$/, 'exact_saved_redirect');
        assert.equal(location.split('/')[2], OWNED.id, 'owned_saved_redirect');
        requestEvidence.redirect_path = location;
        result.accepted_redirects.push({ id: OWNED.id, version: Number(location.split('/').at(-1)), path: location, state: 'SERVER_ACCEPTED_API_NOT_YET_VERIFIED' });
        checkpoint('redirect_destination', p);
        await p.waitForURL(url => savedDestination(url, c.origin, location), { waitUntil: 'domcontentloaded' });
        checkpoint('redirect_arrived', p);
      } else {
        checkpoint('error_summary', p);
        await p.locator('[data-error-summary]').waitFor();
        await p.waitForFunction(() => document.activeElement?.id === 'draft-errors');
        checkpoint('error_summary_focused', p);
      }
    };
    const escaped = async p => {
      assert.equal(await p.locator('main img[onerror], main script').count(), 0, 'entered_text_is_not_markup');
      assert.equal(unsafe, 0, 'no_dialog_or_cross_origin_or_unplanned_write');
    };
    const screenshot = async (p, locator, name) => {
      await escaped(p);
      const bytes = await locator.screenshot({ animations: 'disabled' });
      await fs.writeFile(path.join(c.output, name + '.png'), bytes, { flag: 'wx', mode: 0o600 });
      result.screenshots.push({ file: name + '.png', sha256: sha(bytes) });
    };
    const displayed = async (p, r) => {
      checkpoint('displayed_version_' + r.version, p);
      const card = p.locator(`#record-version-${r.version}`);
      await card.waitFor();
      assert.equal((await card.locator('h2').innerText()), `${r.fields.title} — version ${r.version}`, 'title_page_api_parity');
      const text = await card.innerText();
      for (const value of Object.values(flatten(r.fields))) if (value) assert(text.includes(value), 'field_page_api_parity');
      for (const id of [r.version_id, r.origin.idea.version_id, r.research_context.investigation.version_id, r.research_context.idea_family_association.version_id]) assert(text.includes(id), 'pinned_page_api_parity');
      assert(text.includes(r.draft_completeness === 'complete' ? 'Draft complete' : 'Draft incomplete'), 'completeness_page_api');
      await escaped(p);
    };
    step = 'installed_build';
    const version = await context.request.get(c.origin + '/__staging/version', { maxRedirects: 0 });
    assert.equal(version.status(), 200, 'build_status');
    const buildBytes = await version.body(); assert(buildBytes.includes(Buffer.from(CANDIDATE)), 'exact_installed_commit');
    result.build_response_sha256 = sha(buildBytes); pass(step);
    const seedPath = `/api/v1/hypotheses/${SEED}/versions/1`;
    const seed = await api(seedPath);
    assert.equal(seed.classification, 'synthetic'); assert.equal(seed.version, 1);
    const pins = { idea: seed.origin.idea.version_id, case: seed.research_context.investigation.version_id, binding: seed.research_context.idea_family_association.version_id };
    result.pins = pins;
    const prefix = `BROWSER-${c.runId}`;
    const fields = fullFields(prefix);
    result.expected_complete_fields = fields;
    const rationale = `${prefix} direct invented origin; no research authority.`;
    step = 'owned_record_resume';
    const recordPath = `/api/v1/hypotheses/${recordId}`;
    const first = await api(recordPath + '/versions/1');
    const latestBefore = await api(recordPath);
    const historyBefore = await api(recordPath + '/history');
    assertOwnedBaseline(first, latestBefore, historyBefore);
    // Original create succeeded per operator readback. Do not create or replay it.
    result.preexisting_verified = { id: recordId, version: 1, version_id: first.version_id };
    await navigate(page, `/hypotheses/${recordId}/versions/1`);
    checkSaved(first, { title: OWNED.title }, 1, pins);
    assert.equal(first.draft_completeness, 'incomplete');
    for (const [key, value] of Object.entries(first.fields)) if (key !== 'title') assert.equal(value, null, 'no_invented_defaults');
    await displayed(page, first); pass(step);
    await page.reload({ waitUntil: 'domcontentloaded' }); await displayed(page, first); pass('refresh_saved_incomplete');
    await click(page, page.getByRole('navigation', { name: 'Primary', exact: true }).getByRole('link', { name: 'Home', exact: true }));
    await click(page, page.getByRole('navigation', { name: 'Primary', exact: true }).getByRole('link', { name: 'Hypotheses', exact: true }));
    for (let n = 0; n < 20; n++) {
      const link = page.locator(`a[href="/hypotheses/${recordId}"]`);
      if (await link.count()) { await click(page, link); break; }
      const next = page.getByRole('link', { name: 'Next page', exact: true });
      assert.equal(await next.count(), 1, 'owned_record_reachable'); await click(page, next);
    }
    await displayed(page, first); pass('home_list_reopen');
    step = 'complete_reasoned_revision';
    await click(page, page.getByRole('link', { name: 'Revise hypothesis', exact: true }));
    for (const [name, value] of Object.entries(flatten(fields, '/fields'))) await fill(page, name, value);
    await fill(page, '/correction_reason', `${prefix} complete explicit scientific descriptions; no findings.`);
    await post(page, 303);
    const second = await api(recordPath + '/versions/2'); result.committed.push({ id: recordId, version: 2, version_id: second.version_id });
    checkSaved(second, fields, 2, pins, first); assert.equal(second.draft_completeness, 'complete');
    assert.equal(second.missing_fields.length, 0); await displayed(page, second); pass(step);
    await screenshot(page, page.locator('#record-version-2 > dl').last(), 'complete-owned-fields');
    step = 'stale_owned_input';
    const loser = await context.newPage();
    await navigate(loser, `/hypotheses/${recordId}/revise`);
    await click(page, page.getByRole('link', { name: 'Revise hypothesis', exact: true }));
    const loserTitle = `${prefix} losing input ${MARKER}`;
    await fill(loser, '/fields/title', loserTitle);
    await fill(loser, '/correction_reason', `${prefix} losing reason must stay visible.`);
    const losingInput = await snapshot(loser);
    const winnerFields = { ...fields, title: `${prefix} winning revision ${MARKER}` };
    await fill(page, '/fields/title', winnerFields.title);
    const reason3 = `${prefix} independent explicit title correction.`;
    await fill(page, '/correction_reason', reason3); await post(page, 303);
    const third = await api(recordPath + '/versions/3'); result.committed.push({ id: recordId, version: 3, version_id: third.version_id });
    checkSaved(third, winnerFields, 3, pins, second); assert.equal(third.correction_reason, reason3);
    await post(loser, 409);
    await preserved(loser, losingInput, 'stale_full_input_and_original_key_preserved', true);
    const latestLink = loser.getByRole('link', { name: /^Compare latest record/ });
    assert.equal(await latestLink.getAttribute('target'), '_blank');
    assert.equal(await latestLink.getAttribute('href'), `/hypotheses/${recordId}`);
    await escaped(loser); await screenshot(loser, loser.locator('[data-error-summary]'), 'stale-error');
    await screenshot(loser, control(loser, '/fields/title'), 'stale-owned-title'); pass(step);
    step = 'not_found_owned_input';
    allowMissingCreate = true;
    const missing = await context.newPage();
    await navigate(missing, '/hypotheses/new');
    await fill(missing, '/fields/title', `${prefix} missing-reference draft`);
    await fill(missing, '/fields/claim', `${prefix} unsaved claim ${MARKER}`);
    await fill(missing, '/originating_idea_version_id', `IDEV-${c.runId}`);
    await fill(missing, '/origin_rationale', rationale);
    await fill(missing, '/investigation_version_id', pins.case);
    await fill(missing, '/idea_family_binding/mode', 'existing');
    await fill(missing, '/idea_family_binding/association_version_id', pins.binding);
    const missingInput = await snapshot(missing); await post(missing, 404); allowMissingCreate = false;
    await preserved(missing, missingInput, 'not_found_full_input_and_key_preserved'); await escaped(missing);
    assert.equal(await missing.locator('.status').innerText(), 'No new save confirmed.'); pass(step);
    await screenshot(missing, control(missing, '/fields/claim'), 'not-found-owned-claim');
    step = 'history_original_current_parity';
    await click(page, page.getByRole('link', { name: 'Version history', exact: true }));
    for (const r of [first, second, third]) await displayed(page, r);
    const history = await api(recordPath + '/history');
    assert.deepEqual(history.results.map(r => r.version_id), [first, second, third].map(r => r.version_id), 'only_three_committed_versions');
    assert.deepEqual(immutable(await api(recordPath + '/versions/1')), immutable(first), 'original_snapshot_preserved');
    assert.deepEqual(immutable(await api(recordPath + '/versions/2')), immutable(second), 'complete_snapshot_preserved');
    assert.deepEqual(immutable(await api(recordPath)), immutable(third), 'stale_loser_did_not_replace_latest');
    assert.deepEqual(immutable(await api(seedPath)), immutable(seed), 'seed_immutable_context_preserved'); pass(step);
    await click(page, page.getByRole('link', { name: 'Open exact version 2', exact: true })); await displayed(page, second);
    step = 'narrow_readable_escaped_text';
    await page.setViewportSize({ width: 375, height: 812 });
    const width = await page.evaluate(() => ({ viewport: innerWidth, content: document.documentElement.scrollWidth }));
    assert(width.content <= width.viewport, 'no_horizontal_page_overflow');
    await displayed(page, second); await screenshot(page, page.locator('#record-version-2 > h2'), 'narrow-owned-title'); pass(step);
    await click(page, page.getByRole('navigation', { name: 'Primary', exact: true }).getByRole('link', { name: 'Home', exact: true }));
    await page.getByRole('heading', { name: 'Home', exact: true }).waitFor(); pass('return_home');
    check('bounded_transport', () => { assert.equal(postCount, 4); assert.equal(unsafe, 0); });
    result.result = result.assertions.some(a => a.result === 'FAIL') ? 'FAIL' : 'EDITOR_BROWSER_SMOKE_PASS';
    if (result.result === 'FAIL') process.exitCode = 1;
  } catch (error) {
    const label = String(error.message || '').split('\n')[0];
    result.result = 'FAIL'; result.failure = { step, phase, ...safeLocal(currentPage?.url() || '', c.origin), error_category: error.name === 'TimeoutError' ? (phase === 'redirect_destination' ? 'REDIRECT_TIMEOUT' : 'UI_OR_REQUEST_TIMEOUT') : error.name === 'AssertionError' ? 'ASSERTION_FAILED' : 'OTHER_ERROR', kind: ['TimeoutError', 'AssertionError', 'Error'].includes(error.name) ? error.name : 'Error', assertion: /^[A-Za-z0-9_.:/-]{1,120}$/.test(label) ? label : 'assertion_or_transport_failed_details_redacted' };
    result.assertions.push({ name: step, result: 'FAIL' }); process.exitCode = 1;
  } finally {
    if (browser) await browser.close().catch(() => { result.close_error = true; if (result.result !== 'FAIL') result.result = 'INCONCLUSIVE'; process.exitCode = 1; });
    result.finished_at = new Date().toISOString(); result.attempted_posts = postCount;
    await fs.writeFile(path.join(c.output, 'summary.json'), JSON.stringify(result, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
    process.stdout.write(JSON.stringify({ result: result.result, committed: result.committed, assertions: result.assertions.length }) + '\n');
  }
  return result;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { await run(config(process.argv.slice(2), process.env)); }
  catch { process.stderr.write('Preflight failed; no automatic retry. Sensitive details suppressed.\n'); process.exitCode = 1; }
}
