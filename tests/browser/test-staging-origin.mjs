import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { access, mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { promisify } from 'node:util';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { sameOriginRequest, stagingTarget } from '../../staging/browser/staging-origin.mjs';
import { sameOriginRequest as sourceRunnerSameOrigin, stagingTarget as sourceRunnerTarget } from './staging-origin.mjs';

const execFileAsync = promisify(execFile);

test('source runner resolves the canonical preflight validator', () => {
  assert.strictEqual(sourceRunnerTarget, stagingTarget);
  assert.strictEqual(sourceRunnerSameOrigin, sameOriginRequest);
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

test('source and rebuilt package allow normalized same-origin requests only', async () => {
  const temporary = await mkdtemp(join(process.env.PAPERCLIP_RUN_SCRATCH_DIR || tmpdir(), 'rms-ui01-'));
  try {
    const packageDir = join(temporary, 'package');
    await execFileAsync('bash', ['staging/build-package.sh', packageDir], {
      cwd: fileURLToPath(new URL('../..', import.meta.url)),
    });
    const packageModule = await import(pathToFileURL(join(packageDir, 'browser/staging-origin.mjs')).href);
    const sourceRunner = await readFile(new URL('./test-ui01.mjs', import.meta.url), 'utf8');
    const packageRunner = await readFile(join(packageDir, 'browser/test-ui01.mjs'), 'utf8');
    assert.equal(packageRunner, sourceRunner);
    assert.match(sourceRunner, /page\.route\('\*\*\/\*', route => sameOriginRequest\(route\.request\(\)\.url\(\), origin\)/);
    assert.equal(await readFile(join(packageDir, 'browser/staging-origin.mjs'), 'utf8'),
      await readFile(new URL('../../staging/browser/staging-origin.mjs', import.meta.url), 'utf8'));

    for (const implementation of [sourceRunnerSameOrigin, packageModule.sameOriginRequest]) {
      for (const origin of ['https://example.invalid:443', 'https://EXAMPLE.invalid:8443',
        'https://example.invalid:08443', 'https://example.invalid:8443', 'https://[::1]:8443']) {
        const accepted = stagingTarget(origin).slice(0, -1);
        const sameOriginUrl = new URL('/sources/new', accepted).href;
        assert.equal(implementation(sameOriginUrl, accepted), true, origin);
        assert.equal(implementation('https://elsewhere.invalid/sources/new', accepted), false, origin);
        assert.equal(implementation('http://example.invalid/sources/new', accepted), false, origin);
      }
    }
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test('browser handoff excludes the environment-password desktop helper', async () => {
  const packageBuilder = await readFile(new URL('../../staging/build-package.sh', import.meta.url), 'utf8');
  assert.doesNotMatch(packageBuilder, /open-staging\.mjs|RMS_BROWSER_PASSWORD/);
  await assert.rejects(access(new URL('../../staging/browser/open-staging.mjs', import.meta.url)), { code: 'ENOENT' });
});
