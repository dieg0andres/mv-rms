import { chromium } from 'playwright';

const origin = process.env.RMS_STAGING_ORIGIN;
if (!origin || !/^https:\/\/[^/]+$/.test(origin)) throw new Error('Set the approved RMS_STAGING_ORIGIN without a trailing slash');
const target = `${origin}/`;
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  const response = await page.goto(target, { waitUntil: 'domcontentloaded' });
  if (response?.status() !== 401 || !response.headers()['www-authenticate']?.startsWith('Basic ')) {
    throw new Error('Expected private TLS route and Basic challenge; stop before running Test');
  }
  console.log('Exact private HTTPS origin reachable in headless Chromium; Basic challenge observed.');
} finally {
  await browser.close();
}
