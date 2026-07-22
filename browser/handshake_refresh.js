import fs from "node:fs/promises";
import path from "node:path";

import { collectHandshakeSearchJobs } from "./handshake_collect.js";
import { enrichHandshakeJobs } from "./handshake_enrich.js";

function parseArgs(argv) {
  const options = {
    mode: "",
    jobsPath: "",
    outputPath: "",
    userDataDir: "data/handshake_browser_profile",
    origin: "https://sfsu.joinhandshake.com",
    pages: 3,
    perPage: 25,
    limit: 25,
    headless: true,
  };

  options.mode = argv[0] || "";
  for (let index = 1; index < argv.length; index += 1) {
    const value = argv[index];
    const next = argv[index + 1] || "";
    if (value === "--jobs") options.jobsPath = next;
    else if (value === "--out") options.outputPath = next;
    else if (value === "--user-data-dir") options.userDataDir = next;
    else if (value === "--origin") options.origin = next;
    else if (value === "--pages") options.pages = Number(next);
    else if (value === "--per-page") options.perPage = Number(next);
    else if (value === "--limit") options.limit = Number(next);
    else if (value === "--headless") options.headless = String(next).toLowerCase() !== "false";
    else continue;
    index += 1;
  }

  if (!['collect', 'enrich'].includes(options.mode)) {
    throw new Error("First argument must be collect or enrich.");
  }
  if (!options.outputPath) {
    throw new Error("Expected --out path.");
  }
  if (options.mode === "enrich" && !options.jobsPath) {
    throw new Error("Enrichment requires --jobs path.");
  }
  return options;
}

async function loadPlaywright() {
  const explicitImport = String(process.env.JOB_AGENT_PLAYWRIGHT_IMPORT || "").trim();
  if (explicitImport) return import(explicitImport);
  return import("playwright");
}

function wrapLocator(locator) {
  return {
    count: () => locator.count(),
    nth: (index) => wrapLocator(locator.nth(index)),
    isVisible: () => locator.isVisible().catch(() => false),
    click: (options = {}) => {
      const { timeoutMs, ...playwrightOptions } = options;
      return locator.click({
        ...playwrightOptions,
        timeout: playwrightOptions.timeout ?? timeoutMs,
      });
    },
  };
}

function buildTab(page) {
  return {
    goto: (url) => page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 }),
    playwright: {
      waitForLoadState: ({ state, timeoutMs }) => page.waitForLoadState(state, { timeout: timeoutMs }),
      waitForTimeout: (milliseconds) => page.waitForTimeout(milliseconds),
      evaluate: (callback, argument) => page.evaluate(callback, argument),
      getByRole: (role, options) => wrapLocator(page.getByRole(role, options)),
      domSnapshot: async () => {
        const body = page.locator("body");
        const text = await body.innerText().catch(() => "");
        const aria = await body.ariaSnapshot().catch(() => "");
        return `${aria}\n${text}`;
      },
    },
  };
}

async function assertSignedIn(page, origin) {
  await page.goto(`${origin}/job-search`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(1200);
  const currentUrl = page.url().toLowerCase();
  const hasPasswordInput = (await page.locator('input[type="password"]').count()) > 0;
  if (currentUrl.includes("sign_in") || currentUrl.includes("/login") || hasPasswordInput) {
    throw new Error("Handshake login is required; refresh stopped without replacing intake files.");
  }
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const { chromium } = await loadPlaywright();
  const executablePath = String(process.env.JOB_AGENT_BROWSER_EXECUTABLE || "").trim();
  const launchOptions = {
    headless: options.headless,
    viewport: { width: 1440, height: 960 },
  };
  if (executablePath) launchOptions.executablePath = executablePath;

  await fs.mkdir(options.userDataDir, { recursive: true });
  await fs.mkdir(path.dirname(options.outputPath), { recursive: true });
  const context = await chromium.launchPersistentContext(options.userDataDir, launchOptions);
  const page = context.pages()[0] || await context.newPage();

  try {
    await assertSignedIn(page, options.origin);
    const tab = buildTab(page);
    let jobs;
    if (options.mode === "collect") {
      jobs = await collectHandshakeSearchJobs(tab, {
        origin: options.origin,
        pages: options.pages,
        perPage: options.perPage,
        outputPath: options.outputPath,
      });
      if (jobs.length === 0) {
        const diagnostic = await page.evaluate(() => ({
          url: location.href,
          title: document.title,
          regions: document.querySelectorAll('[role="region"]').length,
          jobHooks: document.querySelectorAll('[data-hook*="job-result"]').length,
          links: Array.from(document.querySelectorAll('a[href]'))
            .map((link) => ({ href: link.getAttribute('href'), text: String(link.textContent || '').trim() }))
            .filter((link) => /job/i.test(`${link.href} ${link.text}`))
            .slice(0, 20),
          bodyText: String(document.body?.innerText || '').replace(/\s+/g, ' ').slice(0, 1200),
        }));
        throw new Error(
          `Handshake returned zero visible job cards; refresh stopped to preserve prior intake. Diagnostic: ${JSON.stringify(diagnostic)}`,
        );
      }
    } else {
      const sourceJobs = JSON.parse(await fs.readFile(options.jobsPath, "utf8"));
      if (!Array.isArray(sourceJobs) || sourceJobs.length === 0) {
        throw new Error("Targeted intake is empty; refresh stopped to preserve prior enriched intake.");
      }
      jobs = await enrichHandshakeJobs(tab, sourceJobs, {
        limit: options.limit,
        outputPath: options.outputPath,
      });
    }

    process.stdout.write(`${JSON.stringify({ mode: options.mode, jobs_written: jobs.length, output: options.outputPath })}\n`);
  } finally {
    await context.close();
  }
}

main().catch((error) => {
  process.stderr.write(`${String(error?.stack || error?.message || error)}\n`);
  process.exitCode = 1;
});
