import fs from "node:fs/promises";

function parseArgs(argv) {
  const options = {
    jobsPath: "",
    outputPath: "",
    userDataDir: "",
    headless: false,
    loginOnly: false,
    transcriptPath: "",
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
    } else if (value === "--transcript-path") {
      options.transcriptPath = argv[index + 1] || "";
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

async function detectSubmittedState(page) {
  const bodyText = normalizeText(await page.locator("body").textContent().catch(() => "")).toLowerCase();
  const submittedSignals = [
    "application submitted",
    "you applied",
    "withdraw application",
    "you've already applied",
    "your application has been submitted",
  ];
  return submittedSignals.some((signal) => bodyText.includes(signal));
}

async function submitControlIsEnabled(page) {
  const control = await findVisibleSubmitControl(page);
  if (!control) {
    return false;
  }
  return control.isEnabled().catch(() => false);
}

async function selectExistingTranscript(page) {
  const controls = page.locator('input[type="radio"], input[type="checkbox"]');
  const count = await controls.count().catch(() => 0);
  for (let index = 0; index < count; index += 1) {
    const control = controls.nth(index);
    const contextText = normalizeText(await control.evaluate((element) => {
      const id = element.getAttribute("id");
      const label = id ? document.querySelector(`label[for="${CSS.escape(id)}"]`) : null;
      return label?.textContent || element.parentElement?.textContent || "";
    }).catch(() => ""));
    if (!/transcript/i.test(contextText)) {
      continue;
    }
    await control.check({ force: true }).catch(() => {});
    if (await submitControlIsEnabled(page)) {
      return true;
    }
  }

  const selects = page.locator("select");
  const selectCount = await selects.count().catch(() => 0);
  for (let index = 0; index < selectCount; index += 1) {
    const select = selects.nth(index);
    const transcriptOption = await select.evaluate((element) => {
      const options = Array.from(element.options || []);
      const match = options.find((option) => /transcript/i.test(String(option.textContent || "")) && option.value);
      return match ? match.value : "";
    }).catch(() => "");
    if (!transcriptOption) {
      continue;
    }
    await select.selectOption(transcriptOption).catch(() => {});
    await page.waitForTimeout(500);
    if (await submitControlIsEnabled(page)) {
      return true;
    }
  }
  return false;
}

async function uploadTranscript(page, transcriptPath) {
  if (!transcriptPath) {
    return false;
  }

  const uploadButtons = [
    page.getByRole("button", { name: /upload new/i }),
    page.getByRole("button", { name: /upload transcript/i }),
    page.getByRole("button", { name: /add transcript/i }),
  ];
  for (const buttons of uploadButtons) {
    const count = await buttons.count().catch(() => 0);
    for (let index = 0; index < count; index += 1) {
      const button = buttons.nth(index);
      if (!(await button.isVisible().catch(() => false))) {
        continue;
      }
      try {
        const [chooser] = await Promise.all([
          page.waitForEvent("filechooser", { timeout: 5000 }),
          button.click({ force: true, timeout: 5000 }),
        ]);
        await chooser.setFiles(transcriptPath);
        await page.waitForTimeout(1200);
        return true;
      } catch {
        // Some Handshake versions expose the file input directly after the button click.
      }
    }
  }

  const fileInputs = page.locator('input[type="file"]');
  const inputCount = await fileInputs.count().catch(() => 0);
  for (let index = 0; index < inputCount; index += 1) {
    const input = fileInputs.nth(index);
    const contextText = normalizeText(await input.evaluate((element) =>
      element.parentElement?.parentElement?.textContent || element.parentElement?.textContent || ""
    ).catch(() => ""));
    if (inputCount > 1 && !/transcript/i.test(contextText)) {
      continue;
    }
    await input.setInputFiles(transcriptPath).catch(() => {});
    await page.waitForTimeout(1200);
    if (await submitControlIsEnabled(page)) {
      return true;
    }
  }
  return false;
}

async function ensureTranscriptAttached(page, transcriptPath) {
  if (await submitControlIsEnabled(page)) {
    return { attached: true, source: "existing" };
  }
  if (await selectExistingTranscript(page)) {
    return { attached: true, source: "existing_selected" };
  }
  const uploaded = await uploadTranscript(page, transcriptPath);
  if (uploaded && await submitControlIsEnabled(page)) {
    return { attached: true, source: "uploaded" };
  }
  return { attached: false, source: transcriptPath ? "upload_failed" : "missing_local_transcript" };
}

async function submitHandshakeJob(page, job, transcriptPath) {
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

  if (await detectSubmittedState(page)) {
    return {
      job_id: job.id,
      attempted: false,
      submitted: true,
      status: "already_submitted",
      notes: ["Handshake already shows this application as submitted; local state was reconciled."],
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
    const transcript = await ensureTranscriptAttached(page, transcriptPath);
    if (!transcript.attached) {
      return {
        job_id: job.id,
        attempted: true,
        submitted: false,
        status: "transcript_required",
        notes: [`The application requires a transcript, but attachment was not confirmed (${transcript.source}).`],
      };
    }
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

  if (!looksSubmitted && submitStillVisible) {
    await safeGoto(page, job.url);
    if (await detectSubmittedState(page)) {
      return {
        job_id: job.id,
        attempted: true,
        submitted: true,
        status: "submitted",
        notes: ["Submission was reconciled by revisiting the job and confirming Handshake's applied state."],
      };
    }
  }

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
      results.push(await submitHandshakeJob(page, job, options.transcriptPath));
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
