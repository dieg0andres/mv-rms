import assert from 'node:assert/strict';
import { createHash, randomUUID } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { chromium } from 'playwright';
import { stagingTarget } from './staging-origin.mjs';

const origin = stagingTarget(process.env.RMS_STAGING_ORIGIN).slice(0, -1);
const candidate = '0fd772a54bbb1bea7962feb77db21a6c7a6c6dd0';
const tree = 'c1219ad5bd24bbb43b11f74938c7b2b4c8e08f77';
const staticDigest = 'da5ead4cf42ccf22845fe39dc9e1e4d0561a93c61db4da58e7bbbcde53b403e8';
const content = Buffer.from('invented increment-one source bytes v1', 'utf8');
const sourceId = `fixture.ui01.${randomUUID()}`;
const reason = 'Correct the fictional publication timestamp.';
const fields = {
  title: 'Fictional volatility note', source_type: 'working_paper',
  citation: 'Example, A. (2026). Fictional volatility note.',
  observed_available_at: '2026-09-01T14:00:00.000Z',
  authors: ['Ada Fiction', 'Ben Example'], publisher: 'Invented Research Press',
  published_at: '2026-08-31T16:00:00.000Z',
  canonical_url: 'https://example.invalid/fictional-volatility-note',
  rights_note: 'Synthetic fixture; no external rights claim.',
};
const corrected = { ...fields, published_at: '2026-09-01T12:00:00.000Z' };
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const contentDigest = digest(content);
const evidence = {
  case: 'UI-01', checklist: 'RMS-SI-1.0 v1.0', candidate, tree, origin,
  fixture: { source_id: sourceId, synthetic: true, byte_length: content.length, content_sha256: contentDigest },
  principal: 'test_editor (editor)', started_at: new Date().toISOString(),
  result: 'INCONCLUSIVE', observations: [], artifacts: {},
};

function check(value, code) {
  if (!value) throw new Error(code);
}

async function screenshot(page, name) {
  const bytes = await page.screenshot({ mask: [page.locator('input[type=file]')], animations: 'disabled' });
  await writeFile(`/results/${name}.png`, bytes, { flag: 'wx' });
  evidence.artifacts[`${name}.png`] = digest(bytes);
}

function safeVersion(version) {
  const { source_version_id, version: number, corrects_source_version_id, corrects_version,
    correction_reason, changed_fields, title, source_type, citation, observed_available_at,
    authors, publisher, published_at, canonical_url, rights_note, synthetic,
    byte_length, content_sha256, created_at, created_by } = version;
  return { source_version_id, version: number, corrects_source_version_id, corrects_version,
    correction_reason, changed_fields, title, source_type, citation, observed_available_at,
    authors, publisher, published_at, canonical_url, rights_note, synthetic,
    byte_length, content_sha256, created_at, created_by };
}

async function pageGet(page, path) {
  const response = await page.goto(`${origin}${path}`, { waitUntil: 'networkidle' });
  check(response?.status() === 200, 'page:unexpected_status');
  evidence.observations.push({ action: `PAGE ${path}`, status: response.status() });
}

async function apiGet(context, path) {
  const response = await context.request.get(`${origin}${path}`, { maxRedirects: 0 });
  check(response.status() === 200, 'api:unexpected_status');
  const body = await response.json();
  check(!JSON.stringify(body).includes(content.toString('base64')), 'api:base64_leak');
  check(!JSON.stringify(body).includes(content.toString()), 'api:content_leak');
  evidence.observations.push({ action: `GET ${path}`, status: 200 });
  return body;
}

async function manifest(context, number) {
  const path = `/api/v1/sources/${sourceId}/manifest?through_version=${number}`;
  const response = await context.request.get(`${origin}${path}`, { maxRedirects: 0 });
  check(response.status() === 200, 'manifest:unexpected_status');
  const bytes = Buffer.from(await response.body());
  const hash = digest(bytes);
  assert.equal(response.headers()['x-manifest-sha256'], hash);
  check(!bytes.includes(content), 'manifest:content_leak');
  check(!bytes.includes(Buffer.from(content.toString('base64'))), 'manifest:base64_leak');
  const parsed = JSON.parse(bytes.toString());
  assert.equal(parsed.schema_version, 1);
  assert.equal(parsed.versions.length, number);
  parsed.versions.forEach((entry, index) => {
    assert.deepEqual(entry, {
      byte_length: content.length, content_sha256: contentDigest,
      corrects_version: index || null, source_id: sourceId,
      synthetic: true, version: index + 1,
    });
  });
  await writeFile(`/results/manifest-v${number}.json`, bytes, { flag: 'wx' });
  evidence.artifacts[`manifest-v${number}.json`] = hash;
  evidence.observations.push({ action: `GET ${path}`, status: 200,
    header_sha256: response.headers()['x-manifest-sha256'], body_sha256: hash, byte_length: bytes.length });
  return bytes;
}

async function submit(page, path, expected, step) {
  const pending = page.waitForResponse(response => response.url() === `${origin}${path}` &&
    response.request().method() === 'POST');
  await page.locator('form[data-rms-form=source] button[type=submit]').click();
  const response = await pending;
  const request = response.request();
  const payload = request.postDataJSON();
  check(/^[0-9a-f-]{36}$/.test(request.headers()['idempotency-key'] || ''), 'submit:missing_key');
  check(request.headers()['content-type']?.startsWith('application/json'), 'submit:wrong_media_type');
  assert.deepEqual({ ...payload, content_base64: null }, expected);
  if (step === 'create') {
    check(typeof payload.content_base64 === 'string', 'submit:missing_content');
    assert.equal(digest(Buffer.from(payload.content_base64, 'base64')), contentDigest);
  } else assert.equal(payload.content_base64, null);
  const observation = { step, action: `POST ${path}`, status: response.status(),
    request: { ...expected, content_base64: step === 'create' ?
      { present: true, byte_length: content.length, sha256: contentDigest } : null,
      idempotency_key_present: true } };
  evidence.observations.push(observation);
  check(response.status() === 201, 'submit:unexpected_status');
  const body = await response.json();
  check(!JSON.stringify(body).includes(content.toString('base64')), 'submit:base64_leak');
  check(!JSON.stringify(body).includes(content.toString()), 'submit:content_leak');
  const status = await page.locator('form[data-rms-form=source] [role=status]').innerText();
  check(status.includes('Saved.'), 'submit:missing_success');
  observation.status_text = status;
  observation.response = { source_id: body.source_id, synthetic: body.synthetic,
    latest_version: body.latest_version, latest_source_version_id: body.latest_source_version_id,
    latest: safeVersion(body.latest) };
  return body;
}

let browser;
let step = 'preflight';
try {
  const password = (await readFile('/run/secrets/test_editor_password', 'utf8')).replace(/\r?\n$/, '');
  check(password.length > 0, 'preflight:missing_password');
  browser = await chromium.launch({ headless: true });
  evidence.browser_version = browser.version();
  const context = await browser.newContext({ httpCredentials: { username: 'test_editor', password } });
  const page = await context.newPage();
  await page.route('**/*', route => new URL(route.request().url()).origin === origin ?
    route.continue() : route.abort());
  await pageGet(page, '/__staging/version');
  check((await page.locator('body').innerText()).includes(candidate), 'preflight:wrong_candidate');
  const asset = await context.request.get(`${origin}/static/rms/rms_forms.js`, { maxRedirects: 0 });
  check(asset.status() === 200, 'preflight:missing_static_js');
  assert.equal(digest(Buffer.from(await asset.body())), staticDigest);
  evidence.observations.push({ action: 'GET /static/rms/rms_forms.js', status: 200, sha256: staticDigest });

  step = 'create';
  await pageGet(page, '/sources/new');
  const form = page.locator('form[data-rms-form=source]');
  assert.equal(await form.getAttribute('data-correction'), 'false');
  await form.locator('[name=source_id]').fill(sourceId);
  for (const [name, value] of Object.entries(fields)) {
    if (name === 'source_type') await form.locator(`[name=${name}]`).selectOption(value);
    else await form.locator(`[name=${name}]`).fill(name === 'authors' ? value.join('\n') : value);
  }
  await form.locator('[name=observed_available_at]').fill('2026-09-01T16:00:00+02:00');
  await form.locator('[name=published_at]').fill('2026-08-31T12:00:00-04:00');
  await form.locator('[name=content_file]').setInputFiles({ name: 'fictional-source.txt', mimeType: 'text/plain', buffer: content });
  await screenshot(page, 'source-create-form');
  const created = await submit(page, '/api/v1/sources',
    { synthetic: true, source_id: sourceId, ...fields, content_base64: null }, 'create');
  assert.equal(created.source_id, sourceId);
  assert.equal(created.latest_version, 1);
  assert.equal(created.latest_source_version_id, created.latest.source_version_id);
  assert.match(created.latest.source_version_id, /^SRCV-[0-9a-f-]{36}$/);
  assert.deepEqual(created.latest.changed_fields, []);
  assert.equal(created.latest.corrects_source_version_id, null);
  assert.equal(created.latest.correction_reason, null);
  assert.equal(created.latest.byte_length, content.length);
  assert.equal(created.latest.content_sha256, contentDigest);
  assert.equal(created.latest.created_by, 'test_editor');
  for (const [name, value] of Object.entries(fields)) {
    assert.deepEqual(created.latest[name], name.endsWith('_at') ? value.replace('.000Z', '.000000Z') : value);
  }
  await screenshot(page, 'source-create-success');
  const sourceV1 = created.latest.source_version_id;
  const firstManifest = await manifest(context, 1);
  const original = await apiGet(context, `/api/v1/sources/${sourceId}`);
  assert.deepEqual(original.latest, created.latest);

  step = 'correct';
  await pageGet(page, `/sources/${sourceId}/correct`);
  assert.equal(await form.getAttribute('data-correction'), 'true');
  assert.equal(await form.locator('[name=expected_latest_version]').inputValue(), '1');
  assert.equal(await form.locator('[name=content_file]').inputValue(), '');
  for (const [name, value] of Object.entries(fields)) {
    assert.equal(await form.locator(`[name=${name}]`).inputValue(), name === 'authors' ? value.join('\n') :
      name.endsWith('_at') ? value.replace('.000Z', '.000000Z') : value);
  }
  await form.locator('[name=published_at]').fill('2026-09-01T12:00:00Z');
  await form.locator('[name=correction_reason]').fill(reason);
  await screenshot(page, 'source-correct-form');
  const changed = await submit(page, `/api/v1/sources/${sourceId}/corrections`,
    { synthetic: true, ...corrected, content_base64: null,
      expected_latest_version: 1, correction_reason: reason }, 'correct');
  assert.equal(changed.source_id, sourceId);
  assert.equal(changed.latest_version, 2);
  assert.notEqual(changed.latest.source_version_id, sourceV1);
  assert.equal(changed.latest.corrects_source_version_id, sourceV1);
  assert.equal(changed.latest.corrects_version, 1);
  assert.equal(changed.latest.correction_reason, reason);
  assert.deepEqual(changed.latest.changed_fields, ['published_at']);
  assert.equal(changed.latest.published_at, '2026-09-01T12:00:00.000000Z');
  assert.equal(changed.latest.created_by, 'test_editor');
  assert.equal(changed.latest.byte_length, content.length);
  assert.equal(changed.latest.content_sha256, contentDigest);
  await screenshot(page, 'source-correct-success');

  step = 'history';
  const history = await apiGet(context, `/api/v1/sources/${sourceId}/versions`);
  assert.equal(history.source_id, sourceId);
  assert.equal(history.versions.length, 2);
  assert.deepEqual(history.versions, [created.latest, changed.latest]);
  evidence.observations.push({ step, versions: history.versions.map(safeVersion) });
  await pageGet(page, `/sources/${sourceId}/history`);
  const rows = page.locator('table tbody tr');
  assert.equal(await rows.count(), 2);
  check((await rows.nth(0).innerText()).includes(sourceV1), 'history:original_missing');
  const secondRow = await rows.nth(1).innerText();
  for (const value of [changed.latest.source_version_id, sourceV1, reason,
    'published_at', changed.latest.created_by, changed.latest.created_at.slice(0, 4)]) {
    check(secondRow.includes(value), 'history:metadata_missing');
  }
  await screenshot(page, 'source-history');
  const retained = await context.request.get(`${origin}/api/v1/sources/${sourceId}/manifest?through_version=1`, { maxRedirects: 0 });
  assert.equal(retained.status(), 200);
  assert.deepEqual(Buffer.from(await retained.body()), firstManifest);
  const secondManifest = await manifest(context, 2);
  assert.notDeepEqual(secondManifest, firstManifest);
  evidence.observations.push({ step: 'preservation', original_source_version_id: sourceV1,
    v1_manifest_unchanged: true, v2_content_digest_unchanged: true });
  evidence.result = 'PASS';
} catch (error) {
  evidence.result = step === 'preflight' ? 'BLOCKED/NOT RUN' : 'FAIL';
  evidence.failure = { step, kind: error.name,
    check: /^[a-z-]+:[a-z_]+$/.test(error.message || '') ? error.message : 'assertion_or_browser_error' };
} finally {
  try { await browser?.close(); } catch { evidence.browser_close_failed = true; }
  evidence.ended_at = new Date().toISOString();
  await writeFile('/results/ui01-evidence.json', JSON.stringify(evidence, null, 2) + '\n', { flag: 'wx' });
}
if (evidence.result !== 'PASS') process.exitCode = 1;
