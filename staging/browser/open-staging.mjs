import { chromium } from 'playwright';

const origin = process.env.RMS_STAGING_ORIGIN;
if (!origin || !/^https:\/\/[^/]+$/.test(origin)) throw new Error('Set the approved RMS_STAGING_ORIGIN without a trailing slash');
const target = `${origin}/`;
const username = process.env.RMS_BROWSER_USERNAME;
const password = process.env.RMS_BROWSER_PASSWORD;
if (!username || !password) {
  throw new Error('Inject RMS_BROWSER_USERNAME and RMS_BROWSER_PASSWORD from approved secret handling');
}
const browser = await chromium.launch({ headless: false });
const context = await browser.newContext({ httpCredentials: { username, password } });
const page = await context.newPage();
await page.goto(target);
console.log(`Opened ${target}; verify the candidate on /__staging/version before testing.`);
await page.pause();
await browser.close();
