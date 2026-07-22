import fs from "node:fs/promises";

function parseArgs(argv) {
  const options = {
    jobsPath: "",
    outputPath: "",
    userDataDir: "",
    headless: false,
    loginOnly: false,
    origin: "https://app.joinhandshake.com",
  };

  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--jobs") {
      options.jobsPath = argv[index + 1] || "";
      index += 1;
    } else if (value === "--out") {
      options.outputPath = argv[index + 1] || "";
      index += 1;
    } else if (value === "--user-data-dir") {
      options.userDataDir = argv[index + 1] || "";
      index += 1;
    } else if (value === "--headless") {
      options.headless = String(argv[index + 1] || "").toLowerCase() === "true";
      index += 1;
    } else if (value === "--login-only") {
      options.loginOnly = String(argv[index + 1] || "").toLowerCase() === "true";
      index += 1;
    } else if (value === "--origin") {
      options.origin = argv[index + 1] || options.origin;
      index += 1;
    }
  }

  if (!options.jobsPath || !options.outputPath || !options.userDataDir) {
    throw new Error("Expected --jobs, --out, and --user-data-dir arguments.");
  }
  return options;
}

function normalizeText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function textLooksLikeVisibleSubmit(value) {
  const text = normalizeText(value).toLowerCase();
  if (!text) {
    return false;
  }
  return (
    text === "submit" ||
    text === "submit application" ||
    text === "submit your application" ||
    text === "apply now" ||
    text === "send application"
  );
}

async function loadPlaywright() {
  const explicitImport = normalizeText(process.env.JOB_AGENT_PLAYWRIGHT_IMPORT || "");
  if (explicitImport) {
    const mod = await import(explicitImport);
    return mod;
  }
  try {
    return await import("playwright");
  } catch {
    return import("playwright-core");
  }
}

async function isLoginRequired(page) {
  const currentUrl = page.url().toLowerCase();
  if (currentUrl.includes("sign_in") || currentUrl.includes("login")) {
    return true;
  }
  const bodyText = normalizeText(await page.locator("body").textContent()).toLowerCase();
  return bodyText.includes("sign in") && bodyText.includes("handshake");
}

async function safeGoto(page, url) {
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
  } catch (error) {
    const message = normalizeText(error?.message || String(error));
    if (!message.toLowerCase().includes("net::err_aborted")) {
      throw error;
    }
  }
  await page.waitForTimeout(1500);
}

async function waitForLoginCompletion(page, origin) {
  process.stdout.write("Handshake login required in the opened browser. Finish signing in there; the runner will keep waiting.\n");
  const deadline = Date.now() + 5 * 60 * 1000;
  while (Date.now() < deadline) {
    await page.waitForTimeout(2000);
    const currentUrl = page.url();
    if (!currentUrl) {
      continue;
    }
    if (!(await isLoginRequired(page))) {
      return true;
    }
    const lowerUrl = currentUrl.toLowerCase();
    if (lowerUrl.includes("saml") || lowerUrl.includes("sso") || lowerUrl.includes("idp")) {
      continue;
    }
    if (lowerUrl.startsWith(origin.toLowerCase()) && !lowerUrl.includes("sign_in")) {
      return true;
    }
  }
  return false;
}

async function waitForUserClose(page) {
  process.stdout.write("Login bootstrap complete. Close the browser window when you're done verifying the session.\n");
  while (!page.isClosed()) {
    try {
      await page.waitForTimeout(1000);
    } catch (error) {
      const message = normalizeText(error?.message || String(error)).toLowerCase();
      if (page.isClosed() || message.includes("target page, context or browser has been closed")) {
        break;
      }
      throw error;
    }
  }
}

async function clickVisibleButton(page, name) {
  const buttons = page.getByRole("button", { name });
  const count = await buttons.count();
  for (let index = 0; index < count; index += 1) {
    const candidate = buttons.nth(index);
    if (await candidate.isVisible()) {
      await candidate.click({ force: true, timeout: 5000 });
      return true;
    }
  }
  return false;
}

async function clickVisibleButtonByPattern(page, pattern) {
  const buttons = page.getByRole("button", { name: pattern });
  const count = await buttons.count();
  for (let index = 0; index < count; index += 1) {
    const candidate = buttons.nth(index);
    if (await candidate.isVisible()) {
      await candidate.click({ force: true, timeout: 5000 });
      return true;
    }
  }
  return false;
}

async function waitForApplySurface(page) {
  const deadline = Date.now() + 7000;
  while (Date.now() < deadline) {
    const dialogVisible = await page.locator('[role="dialog"]').first().isVisible().catch(() => false);
    const submitVisible = await hasVisibleSubmitControl(page);
    const externalVisible = await hasVisibleExternalApply(page);
    if (dialogVisible || submitVisible || externalVisible) {
      return true;
    }
    await page.waitForTimeout(400);
  }
  return false;
}

async function hasVisibleExternalApply(page) {
  const externalControls = [
    page.getByRole("button", { name: /Apply externally/i }),
    page.getByRole("link", { name: /Apply externally/i }),
    page.getByText(/View application/i),
  ];
  for (const locator of externalControls) {
    const count = await locator.count().catch(() => 0);
    for (let index = 0; index < count; index += 1) {
      if (await locator.nth(index).isVisible().catch(() => false)) {
        return true;
      }
    }
  }
  return false;
}

async function findVisibleSubmitControl(page) {
  const buttonPatterns = [/Submit Application/i, /Submit Your Application/i, /^Submit$/i, /Apply Now/i];
  for (const pattern of buttonPatterns) {
    const locator = page.getByRole("button", { name: pattern });
    const count = await locator.count().catch(() => 0);
    for (let index = 0; index < count; index += 1) {
      const candidate = locator.nth(index);
      if (await candidate.isVisible().catch(() => false)) {
        return candidate;
      }
    }
  }

  const submitInputs = page.locator('input[type="submit"], button[type="submit"], [data-testid*="submit"]');
  const controlCount = await submitInputs.count().catch(() => 0);
  for (let index = 0; index < controlCount; index += 1) {
    const candidate = submitInputs.nth(index);
    if (!(await candidate.isVisible().catch(() => false))) {
      continue;
    }
    const text = normalizeText(await candidate.textContent().catch(() => ""));
    const value = normalizeText(await candidate.getAttribute("value").catch(() => ""));
    if (textLooksLikeVisibleSubmit(text) || textLooksLikeVisibleSubmit(value) || (!text && !value)) {
      return candidate;
    }
  }

  return null;
}

async function hasVisibleSubmitControl(page) {
  return (await findVisibleSubmitControl(page)) !== null;
}

async function captureModalState(page) {
  const dialog = page.locator('[role="dialog"]').first();
  const dialogText = normalizeText(await dialog.textContent().catch(() => ""));
  const bodyText = normalizeText(await page.locator("body").textContent());
  const combinedText = normalizeText(`${dialogText} ${bodyText}`);
  return {
    requiresResume: combinedText.includes("Attach your resume") || combinedText.includes("requires a resume"),
    requiresTranscript:
      combinedText.includes("Attach your transcript") || combinedText.includes("requires a transcript"),
    requiresCoverLetter:
      combinedText.includes("Attach your cover letter") || combinedText.includes("requires a cover letter"),
    hasSubmitButton: await hasVisibleSubmitControl(page),
    bodyText: combinedText,
  };
}

async function submitHandshakeJob(page, job) {
  await safeGoto(page, job.url);

  if (await isLoginRequired(page)) {
    return {
      job_id: job.id,
      attempted: false,
      submitted: false,
      status: "login_required",
      notes: ["Handshake login is required in the local browser profile before submissions can continue."],
    };
  }

  const externalApply = await clickVisibleButtonByPattern(page, /Apply externally/i);
  if (externalApply) {
    return {
      job_id: job.id,
      attempted: false,
      submitted: false,
      status: "external_review_required",
      notes: ["This job redirects externally and should stay in Checkin/Review."],
    };
  }

  const applyClicked =
    (await clickVisibleButtonByPattern(page, /^Apply$/i)) ||
    (await clickVisibleButtonByPattern(page, /^Easy Apply$/i)) ||
    (await clickVisibleButtonByPattern(page, /^Quick Apply$/i));
  if (!applyClicked) {
    return {
      job_id: job.id,
      attempted: false,
      submitted: false,
      status: "apply_button_not_found",
      notes: ["Could not find a visible Handshake Apply button on the page."],
    };
  }

  await waitForApplySurface(page);
  const modalState = await captureModalState(page);

  if (await hasVisibleExternalApply(page)) {
    return {
      job_id: job.id,
      attempted: true,
      submitted: false,
      status: "external_review_required",
      notes: ["The job opened an external or already-started application flow and should stay in Checkin/Review."],
    };
  }

  if (modalState.requiresCoverLetter) {
    return {
      job_id: job.id,
      attempted: true,
      submitted: false,
      status: "cover_letter_required",
      notes: ["The application modal requires a cover letter, so the runner skipped submission."],
    };
  }

  if (modalState.requiresTranscript) {
    return {
      job_id: job.id,
      attempted: true,
      submitted: false,
      status: "transcript_required",
      notes: ["The application modal requires a transcript attachment and needs review."],
    };
  }

  if (!modalState.hasSubmitButton) {
    return {
      job_id: job.id,
      attempted: true,
      submitted: false,
      status: "submit_button_not_found",
      notes: ["The application modal opened, but no Submit Application button was found."],
    };
  }

  const submitControl = await findVisibleSubmitControl(page);
  if (!submitControl) {
    return {
      job_id: job.id,
      attempted: true,
      submitted: false,
      status: "submit_button_not_found",
      notes: ["The application surface was visible, but no clickable submit control could be resolved."],
    };
  }

  const beforeUrl = page.url();
  const beforeBodyText = normalizeText(await page.locator("body").textContent()).toLowerCase();
  await submitControl.click({ force: true, timeout: 5000 });
  await page.waitForTimeout(2200);

  const bodyTextAfter = normalizeText(await page.locator("body").textContent()).toLowerCase();
  const submitStillVisible = await hasVisibleSubmitControl(page);
  const currentUrl = page.url();
  const looksSubmitted =
    bodyTextAfter.includes("application submitted") ||
    bodyTextAfter.includes("you applied") ||
    bodyTextAfter.includes("withdraw application") ||
    bodyTextAfter.includes("application complete") ||
    bodyTextAfter.includes("application received") ||
    bodyTextAfter.includes("you've already applied") ||
    bodyTextAfter.includes("your application has been submitted") ||
    (beforeUrl !== currentUrl && !currentUrl.toLowerCase().includes("/login")) ||
    (beforeBodyText.includes("submit application") && !bodyTextAfter.includes("submit application"));

  return {
    job_id: job.id,
    attempted: true,
    submitted: looksSubmitted || !submitStillVisible,
    status: looksSubmitted || !submitStillVisible ? "submitted" : "submit_uncertain",
    notes: looksSubmitted || !submitStillVisible
      ? ["Handshake submit flow completed in the local browser."]
      : ["Submit was clicked, but the page did not show a clear success signal."],
  };
}

async function main() {
  const { chromium } = await loadPlaywright();
  const options = parseArgs(process.argv.slice(2));
  const jobs = JSON.parse(await fs.readFile(options.jobsPath, "utf8"));
  await fs.mkdir(options.userDataDir, { recursive: true });
  const executablePath = normalizeText(process.env.JOB_AGENT_BROWSER_EXECUTABLE || "");

  const launchOptions = {
    headless: options.headless,
    viewport: { width: 1440, height: 960 },
  };
  if (executablePath) {
    launchOptions.executablePath = executablePath;
  }

  const context = await chromium.launchPersistentContext(options.userDataDir, launchOptions);

  let page = context.pages()[0];
  if (!page) {
    page = await context.newPage();
  }

  const results = [];
  try {
    await safeGoto(page, options.origin);
    if (await isLoginRequired(page)) {
      const loggedIn = await waitForLoginCompletion(page, options.origin);
      if (!loggedIn) {
        throw new Error("Timed out waiting for Handshake login to complete in the local browser.");
      }
      await safeGoto(page, options.origin);
    }

    if (options.loginOnly) {
      await waitForUserClose(page);
      return;
    }

    for (const job of jobs) {
      results.push(await submitHandshakeJob(page, job));
    }
  } finally {
    await fs.writeFile(options.outputPath, `${JSON.stringify(results, null, 2)}\n`, "utf8");
    await context.close();
  }
}

main().catch((error) => {
  const message = normalizeText(error?.stack || error?.message || String(error));
  process.stderr.write(`${message}\n`);
  process.exitCode = 1;
});
