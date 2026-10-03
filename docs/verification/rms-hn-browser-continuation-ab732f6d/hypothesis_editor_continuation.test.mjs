import assert from 'node:assert/strict';
import test from 'node:test';
import { OWNED, savedDestination, safeLocal, networkCategory, allowedPost,
  assertOwnedBaseline } from './hypothesis_editor_continue_529e638.mjs';

const origin = 'https://invented-browser.example.invalid';
const location = `/hypotheses/${OWNED.id}/versions/1`;

test('normal inherited form fragment defeats old exact wait but matches exact saved resource', () => {
  // The form context-return link supplies this fragment. RFC9110 Location
  // semantics retain it on a303 whose Location has no fragment.
  const actual = origin + location + '#hypothesis-fields';
  assert.notEqual(actual, origin + location);
  assert.equal(savedDestination(actual, origin, location), true);
  assert.equal(savedDestination(origin + location, origin, location), true);
  for (const raw of [
    'https://other.example.invalid' + location,
    origin + location + '?unexpected=1',
    origin + location.replace('/versions/1', '/versions/2'),
    origin + location + '#unbound-fragment',
  ]) assert.equal(savedDestination(raw, origin, location), false);
});

test('continuation admits only owned query-free revisions and one bounded missing-reference route', () => {
  const revise = origin + `/hypotheses/${OWNED.id}/revise`;
  for (let n = 0; n < 4; n++) assert.equal(allowedPost(revise, origin, OWNED.id, n), true);
  assert.equal(allowedPost(revise, origin, OWNED.id, 4), false);
  assert.equal(allowedPost(revise + '?version=1', origin, OWNED.id, 0), false);
  assert.equal(allowedPost(revise, origin, 'HYP-unreviewed', 0), false);
  assert.equal(allowedPost(revise.replace(origin, 'https://other.example.invalid'), origin, OWNED.id, 0), false);
  assert.equal(allowedPost(origin + '/hypotheses/new', origin, OWNED.id, 0), false);
  assert.equal(allowedPost(origin + '/hypotheses/new', origin, OWNED.id, 3, true), true);
  assert.equal(allowedPost(origin + '/hypotheses/new?idea_id=unbound', origin, OWNED.id, 3, true), false);
  assert.equal(allowedPost(origin + '/hypotheses/new', origin, OWNED.id, 4, true), false);
});

test('actual owned v1 identity and unchanged latest/history are required before writes', () => {
  const first = { hypothesis_id: OWNED.id, version_id: OWNED.version_id, version: 1,
    fields: { title: OWNED.title }, classification: 'synthetic' };
  const history = { results: [first] };
  assertOwnedBaseline(first, structuredClone(first), history);
  assert.throws(() => assertOwnedBaseline(first, { ...first, version: 2 }, history));
  assert.throws(() => assertOwnedBaseline(first, first, { results: [first, first] }));
  assert.throws(() => assertOwnedBaseline({ ...first, hypothesis_id: 'HYP-other' }, first, history));
  assert.throws(() => assertOwnedBaseline({ ...first, version_id: 'HYPV-other' }, first, history));
  assert.throws(() => assertOwnedBaseline({ ...first, fields: { title: 'Changed title' } }, first, history));
});

test('diagnostics strip origins, query values and arbitrary fragments and emit network enums only', () => {
  const output = safeLocal(origin + location + '?password=DO_NOT_PRINT#secret=DO_NOT_PRINT', origin);
  assert.equal(output.current_local_url, location + '#redacted');
  assert(!JSON.stringify(output).includes('DO_NOT_PRINT'));
  assert(!JSON.stringify(output).includes(origin));
  assert.equal(safeLocal('', origin).current_local_url, '[other-or-no-origin]');
  assert.equal(safeLocal('about:blank', origin).current_local_url, '[other-or-no-origin]');
  assert.equal(safeLocal('https://other.example.invalid/private?token=x', origin).current_local_url, '[other-or-no-origin]');
  assert.equal(safeLocal(origin + '/secret/path?token=x', origin).current_local_url, '[redacted-local-path]');
  assert.equal(networkCategory('net::ERR_ABORTED'), 'ABORTED');
  assert.equal(networkCategory('net::ERR_CERT_AUTHORITY_INVALID private-host'), 'TLS');
  assert.equal(networkCategory('arbitrary-secret-error'), 'OTHER_NETWORK');
});
