import assert from 'node:assert/strict';
import { access, readFile } from 'node:fs/promises';
import { test } from 'node:test';
import { stagingTarget } from '../../staging/browser/staging-origin.mjs';
import { stagingTarget as sourceRunnerTarget } from './staging-origin.mjs';

test('source runner resolves the canonical preflight validator', () => {
  assert.strictEqual(sourceRunnerTarget, stagingTarget);
});

test('requires a literal HTTPS origin with an explicit valid port', () => {
  for (const origin of ['https://example.invalid:8443', 'https://example.invalid:443', 'https://127.0.0.1:8443', 'https://[::1]:8443']) {
    assert.equal(stagingTarget(origin), `${origin}/`);
  }
  for (const origin of [undefined, '', 'http://example.invalid:8443', 'https://example.invalid',
    'https://example.invalid:', 'https://example.invalid:0', 'https://example.invalid:65536',
    'https://example.invalid:8443/', 'https://example.invalid:8443/path',
    'https://example.invalid:8443?x=1', 'https://example.invalid:8443#fragment',
    'https://user@example.invalid:8443', 'https://user:secret@example.invalid:8443',
    'https://example.invalid:8443@elsewhere.invalid:8443', 'https://example.invalid:8443 ',
    'https://example.invalid:8443\\elsewhere.invalid']) {
    assert.throws(() => stagingTarget(origin), error => {
      assert.match(error.message, /approved https:\/\/host:port/);
      assert.doesNotMatch(error.message, /user|secret|example\.invalid|elsewhere\.invalid/);
      return true;
    });
  }
});

test('browser handoff excludes the environment-password desktop helper', async () => {
  const packageBuilder = await readFile(new URL('../../staging/build-package.sh', import.meta.url), 'utf8');
  assert.doesNotMatch(packageBuilder, /open-staging\.mjs|RMS_BROWSER_PASSWORD/);
  await assert.rejects(access(new URL('../../staging/browser/open-staging.mjs', import.meta.url)), { code: 'ENOENT' });
});
