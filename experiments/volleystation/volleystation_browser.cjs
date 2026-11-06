// One browser and cookie jar per scraper process. Requests are handled serially.
const readline = require('node:readline');
const puppeteer = require('puppeteer-extra');
puppeteer.use(require('puppeteer-extra-plugin-stealth')());

async function main() {
  const browser = await puppeteer.launch({
    headless: process.env.VS_HEADLESS !== 'false',
    ...(process.env.VS_PROFILE_DIR ? { userDataDir: process.env.VS_PROFILE_DIR } : {}),
    ...(process.env.VS_NO_SANDBOX === 'true'
      ? { args: ['--no-sandbox', '--disable-setuid-sandbox'] } : {}),
  });
  try {
    const page = await browser.newPage();
    let latestResponse;
    page.on('response', response => {
      if (response.request().isNavigationRequest() && response.frame() === page.mainFrame()) {
        latestResponse = response;
      }
    });
    await page.setViewport({ width: 1366, height: 768 });
    await page.setExtraHTTPHeaders({ 'Accept-Language': 'pl-PL,pl;q=0.9,en;q=0.8' });
    const lines = readline.createInterface({ input: process.stdin });
    for await (const line of lines) {
      try {
        const { url } = JSON.parse(line);
        latestResponse = null;
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
        // Allow a JS challenge to finish, but never automate an interactive CAPTCHA.
        await page.waitForFunction(() => !document.querySelector(
          '#challenge-running, #challenge-stage, #challenge-form'
        ) && !/just a moment|verify you are human/i.test(document.title),
        { timeout: 20000 }).catch(() => {});
        const status = latestResponse ? latestResponse.status() : 0;
        const headers = latestResponse ? latestResponse.headers() : {};
        process.stdout.write(JSON.stringify({ status, headers, html: await page.content() }) + '\n');
      } catch (error) {
        process.stdout.write(JSON.stringify({ error: error.message }) + '\n');
      }
    }
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
