import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const port = process.env.RMS_DASHBOARD_FIXTURE_PORT ?? '8765';
assert.match(port, /^\d{1,5}$/);
const origin = `http://127.0.0.1:${port}`;
const browser = await chromium.launch();

async function pageFor(username) {
  const context = await browser.newContext({
    viewport: { width: 360, height: 800 },
    httpCredentials: { username, password: 'invented-dashboard-only', origin },
  });
  await context.route('**/*', route => {
    if (new URL(route.request().url()).origin === origin) return route.continue();
    return route.abort();
  });
  return context.newPage();
}

async function doesNotOverflow(page) {
  const viewport = await page.evaluate(() => [document.documentElement.clientWidth, document.documentElement.scrollWidth]);
  assert.deepEqual(viewport, [360, 360]);
}

try {
  const viewer = await pageFor('founder_viewer');
  assert.equal((await viewer.goto(origin)).status(), 200);
  assert.equal((await viewer.request.get(`${origin}/static/rms/navigation.css`)).status(), 200);
  await viewer.keyboard.press('Tab');
  assert.equal(await viewer.locator(':focus').textContent(), 'Skip to main content');
  const focusOutline = await viewer.locator(':focus').evaluate(element => getComputedStyle(element).outlineStyle);
  assert.notEqual(focusOutline, 'none');
  await viewer.keyboard.press('Enter');
  assert.equal(await viewer.locator(':focus').getAttribute('id'), 'main-content');
  const link = viewer.getByRole('link', { name: 'Founder dashboard', exact: true });
  for (let step = 0; step < 8 && !(await link.evaluate(element => element === document.activeElement)); step++) {
    await viewer.keyboard.press('Tab');
  }
  assert.equal(await viewer.locator(':focus').textContent(), 'Founder dashboard');
  await viewer.keyboard.press('Enter');
  await viewer.getByRole('heading', { level: 1, name: 'Founder dashboard' }).waitFor();
  await doesNotOverflow(viewer);
  assert.match(await viewer.getByRole('region', { name: 'Early closures' }).innerText(), /Visible invented examples: 0/);
  assert.match(await viewer.getByRole('region', { name: 'Countable full-validation cycles' }).innerText(), /Real credit from these examples: 0/);
  assert.match(await viewer.getByRole('region', { name: 'Qualifications' }).innerText(), /Real credit from these examples: 0/);
  assert.doesNotMatch(await viewer.content(), /Editor-only spruce example|Hidden \w+ sentinel/);
  assert.equal(await viewer.locator('form').count(), 0);

  const editor = await pageFor('editor');
  assert.equal((await editor.goto(`${origin}/founder-dashboard`)).status(), 200);
  await doesNotOverflow(editor);
  assert.match(await editor.getByRole('region', { name: 'Early closures' }).innerText(), /Visible invented examples: 1/);
  assert.equal(await editor.getByRole('heading', { name: 'Editor-only spruce example' }).count(), 1);
  assert.doesNotMatch(await editor.content(), /Hidden \w+ sentinel/);

  const denied = await pageFor('unassigned');
  const response = await denied.goto(`${origin}/founder-dashboard?role=editor&scope=all`);
  assert.equal(response.status(), 403);
  assert.equal(response.headers()['cache-control'], 'private, no-store');
  await denied.getByRole('heading', { name: 'Access required' }).waitFor();
  assert.doesNotMatch(await denied.content(), /Workflow ledgers|Visible invented examples|Hidden \w+ sentinel/);
  console.log('PASS: Home-to-dashboard keyboard flow, focus, 360px layout, independent example counts, and denied-role isolation.');
} finally {
  await browser.close();
}
