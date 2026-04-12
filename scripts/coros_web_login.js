/**
 * COROS Training Hub Web Login via Playwright
 * 
 * Gets the CPL-coros-token cookie (web API access token) by automating browser login.
 * 
 * Usage:
 *   node coros_web_login.js [email] [password]
 *
 * Output:
 *   - Prints the CPL-coros-token cookie value (the web API token)
 *   - Saves cookies to ~/.openclaw/workspace/skills/coros-data-skill/.coros_web_session
 *
 * Notes:
 *   - The CPL-coros-token cookie value is the COROS_WEB_TOKEN needed for web API calls
 *   - The web token expires much slower than the mobile token
 *   - This script handles the privacy policy checkbox which blocks normal login automation
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const DEFAULT_EMAIL = process.env.COROS_EMAIL;
const DEFAULT_PASSWORD = process.env.COROS_PASSWORD;
const COOKIE_FILE = path.join(__dirname, '..', '.coros_web_session');

async function login(email, password) {
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage']
  });

  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 }
  });
  const page = await context.newPage();

  console.error('Navigating to COROS Training Hub...');
  await page.goto('https://trainingcn.coros.com/login', {
    waitUntil: 'domcontentloaded',
    timeout: 30000
  });
  await page.waitForTimeout(2000);

  // Fill login form
  await page.fill('input[type="text"]', email);
  await page.fill('input[type="password"]', password);

  // The privacy policy checkbox is hidden — use JS to check it directly
  await page.evaluate(() => {
    const checkboxes = document.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(cb => {
      cb.checked = true;
      cb.dispatchEvent(new Event('change', { bubbles: true }));
    });
  });

  await page.waitForTimeout(500);

  // Submit login
  await Promise.all([
    page.waitForNavigation({ timeout: 15000 }).catch(() => {}),
    page.click('button[type="submit"]')
  ]);

  await page.waitForTimeout(5000);

  if (page.url().includes('login')) {
    throw new Error('Login failed — still on login page');
  }

  // Extract CPL-coros-token cookie
  const cookies = await context.cookies();
  const tokenCookie = cookies.find(c => c.name === 'CPL-coros-token');

  if (!tokenCookie) {
    throw new Error('CPL-coros-token cookie not found after login');
  }

  // Save session cookies for reuse
  const sessionData = {
    cookies: cookies.map(c => ({ name: c.name, value: c.value, domain: c.domain })),
    timestamp: Date.now()
  };
  fs.writeFileSync(COOKIE_FILE, JSON.stringify(sessionData));

  await browser.close();
  return tokenCookie.value;
}

if (require.main === module) {
  const email = process.argv[2] || DEFAULT_EMAIL;
  const password = process.argv[3] || DEFAULT_PASSWORD;

  login(email, password)
    .then(token => {
      console.log(token);
    })
    .catch(err => {
      console.error('Login error:', err.message);
      process.exit(1);
    });
}

module.exports = { login };
