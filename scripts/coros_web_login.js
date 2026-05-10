/**
 * COROS Training Hub Web Login via Playwright
 * 
 * Gets the CPL-coros-token cookie (web API access token) by automating browser login.
 * 
 * Usage:
 *   COROS_EMAIL=user@example.com node coros_web_login.js --write-env
 *
 * Output:
 *   - Saves cookies to ../.coros_web_session with 0600 permissions
 *   - Prints the token only when --print-token is passed
 *
 * Notes:
 *   - The CPL-coros-token cookie value is the COROS_WEB_TOKEN needed for web API calls
 *   - The web token expires much slower than the mobile token
 *   - Chromium sandboxing is disabled by default for constrained VM compatibility
 *   - Set COROS_PLAYWRIGHT_SANDBOX=1 to opt back into sandboxing on capable hosts
 *   - This script handles the privacy policy checkbox which blocks normal login automation
 */

const fs = require('fs');
const path = require('path');
const readline = require('readline/promises');

let chromium;
try {
  ({ chromium } = require('playwright'));
} catch (error) {
  if (error.code === 'MODULE_NOT_FOUND') {
    console.error('Missing Node dependency playwright; install it with: cd scripts && npm install');
    process.exit(1);
  }
  throw error;
}

const DEFAULT_EMAIL = process.env.COROS_EMAIL;
const DEFAULT_PASSWORD = process.env.COROS_PASSWORD;
const COOKIE_FILE = path.join(__dirname, '..', '.coros_web_session');
const ENV_FILE = path.join(__dirname, '..', '.coros.env');

function envTruthy(name) {
  return ['1', 'true', 'yes', 'on'].includes(String(process.env[name] || '').trim().toLowerCase());
}

function shellQuote(value) {
  return `'${String(value).replace(/'/g, `'\"'\"'`)}'`;
}

function ensureSecretFilePermissions(file) {
  if (!fs.existsSync(file)) return;
  const mode = fs.statSync(file).mode & 0o077;
  if (mode !== 0) {
    throw new Error(`${file} is readable by group/others; run: chmod 600 ${file}`);
  }
}

function writeSecretFile(file, content) {
  ensureSecretFilePermissions(file);
  const fd = fs.openSync(file, 'w', 0o600);
  try {
    fs.writeFileSync(fd, content, { encoding: 'utf8' });
  } finally {
    fs.closeSync(fd);
  }
  fs.chmodSync(file, 0o600);
}

function writeEnvValue(key, value) {
  ensureSecretFilePermissions(ENV_FILE);
  const lines = fs.existsSync(ENV_FILE)
    ? fs.readFileSync(ENV_FILE, 'utf8').split(/\r?\n/).filter((line, index, array) => index < array.length - 1 || line !== '')
    : [];
  const replacement = `export ${key}=${shellQuote(value)}`;
  let replaced = false;
  const nextLines = [];
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith(`${key}=`) || trimmed.startsWith(`export ${key}=`)) {
      if (!replaced) {
        nextLines.push(replacement);
        replaced = true;
      }
      continue;
    }
    nextLines.push(line);
  }
  if (!replaced) nextLines.push(replacement);
  writeSecretFile(ENV_FILE, `${nextLines.join('\n').replace(/\s+$/u, '')}\n`);
}

function formatLoginError(error) {
  const message = String(error && error.message ? error.message : error);
  if (message.includes("Executable doesn't exist")) {
    return 'Playwright browser is missing; run: cd scripts && npx playwright install chromium';
  }
  const libraryMatch = message.match(/error while loading shared libraries: ([^:]+):/);
  if (libraryMatch) {
    return `Playwright browser dependency missing (${libraryMatch[1]}); run: cd scripts && npx playwright install-deps chromium`;
  }
  return message;
}

async function promptHidden(query) {
  if (!process.stdin.isTTY) {
    throw new Error('Missing COROS_PASSWORD; set it in the environment or run interactively');
  }
  const rl = readline.createInterface({ input: process.stdin, output: process.stderr });
  process.stderr.write(query);
  process.stdin.setRawMode?.(false);
  const wasRaw = process.stdin.isRaw;
  try {
    await new Promise((resolve, reject) => {
      const stty = require('child_process').spawn('stty', ['-echo'], { stdio: ['inherit', 'ignore', 'ignore'] });
      stty.on('exit', resolve);
      stty.on('error', reject);
    });
    const answer = await rl.question('');
    process.stderr.write('\n');
    return answer;
  } finally {
    if (wasRaw) process.stdin.setRawMode?.(true);
    await new Promise((resolve) => {
      const stty = require('child_process').spawn('stty', ['echo'], { stdio: ['inherit', 'ignore', 'ignore'] });
      stty.on('exit', resolve);
      stty.on('error', resolve);
    });
    rl.close();
  }
}

async function login(email, password) {
  const useSandbox = envTruthy('COROS_PLAYWRIGHT_SANDBOX');
  const launchArgs = ['--disable-dev-shm-usage'];
  if (!useSandbox) {
    launchArgs.push('--no-sandbox');
  }
  const browser = await chromium.launch({
    headless: true,
    args: launchArgs,
    chromiumSandbox: useSandbox
  });

  try {
    const context = await browser.newContext({
      viewport: { width: 1280, height: 900 }
    });
    const page = await context.newPage();

    console.error('Navigating to COROS Training Hub...');
    await page.goto('https://training.coros.com/login', {
      waitUntil: 'domcontentloaded',
      timeout: 30000
    });
    await page.waitForTimeout(2000);

    // Fill login form
    await page.fill('input[type="text"]', email);
    await page.fill('input[type="password"]', password);

    // The privacy policy checkbox is hidden; use JS to check it directly.
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
      throw new Error('Login failed - still on login page');
    }

    // Extract CPL-coros-token cookie
    const cookies = await context.cookies();
    const tokenCookie = cookies.find(c => c.name === 'CPL-coros-token');

    if (!tokenCookie) {
      throw new Error('CPL-coros-token cookie not found after login');
    }

    // Save session cookies for reuse.
    const sessionData = {
      cookies: cookies.map(c => ({ name: c.name, value: c.value, domain: c.domain })),
      timestamp: Date.now()
    };
    writeSecretFile(COOKIE_FILE, JSON.stringify(sessionData));

    return tokenCookie.value;
  } finally {
    await browser.close();
  }
}

if (require.main === module) {
  const args = new Set(process.argv.slice(2));
  const email = DEFAULT_EMAIL;

  (async () => {
    if (!email) {
      throw new Error('Missing COROS_EMAIL');
    }
    const password = DEFAULT_PASSWORD || await promptHidden('COROS password: ');
    const token = await login(email, password);
    if (args.has('--write-env')) {
      writeEnvValue('COROS_WEB_TOKEN', token);
      console.error(`Wrote COROS_WEB_TOKEN to ${ENV_FILE}`);
    }
    if (args.has('--print-token')) {
      console.log(token);
    }
    if (!args.has('--write-env') && !args.has('--print-token')) {
      console.error('Web token obtained. Re-run with --write-env to store it or --print-token to display it.');
    }
  })()
    .then(token => {
      return token;
    })
    .catch(err => {
      console.error('Login error:', formatLoginError(err));
      process.exit(1);
    });
}

module.exports = { login, writeEnvValue, writeSecretFile, formatLoginError };
