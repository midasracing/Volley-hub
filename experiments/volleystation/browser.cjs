const readline = require('node:readline');
const engine = process.argv[2];
async function main() {
  const puppeteer = engine === 'stealth'
    ? require('puppeteer-extra') : require('rebrowser-puppeteer');
  if (engine === 'stealth') puppeteer.use(require('puppeteer-extra-plugin-stealth')());
  const args = process.env.LAB_NO_SANDBOX === 'true' ? ['--no-sandbox'] : [];
  if (process.env.LAB_PROXY) args.push(`--proxy-server=${process.env.LAB_PROXY}`);
  const browser = await puppeteer.launch({
    executablePath: process.env.LAB_BROWSER || '/usr/bin/chromium',
    headless: process.env.LAB_HEADFUL !== 'true',
    userDataDir: process.env.LAB_PROFILE,
    args,
  });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1366, height: 768 });
    const lines = readline.createInterface({ input: process.stdin });
    for await (const line of lines) {
      let lastResponse;
      const capture = response => {
        if (response.request().isNavigationRequest() && response.frame() === page.mainFrame()) lastResponse = response;
      };
      page.on('response', capture);
      try {
        const { url } = JSON.parse(line);
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 35000 });
        await page.waitForFunction(() => !/just a moment|verify you are human|attention required|cierpliwości|cierpliwosci|chwileczkę/i.test(document.title)
          && !document.querySelector('#challenge-running, #challenge-stage, #challenge-form'),
          { timeout: 15000 }).catch(() => {});
        console.log(JSON.stringify({ status: lastResponse?.status(), headers: lastResponse?.headers() || {},
          html: await page.content(), final_url: page.url(), browser: await browser.version() }));
      } catch (error) {
        console.log(JSON.stringify({ error: error.message }));
      } finally {
        page.off('response', capture);
      }
    }
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
