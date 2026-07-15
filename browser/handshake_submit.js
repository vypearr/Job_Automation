import fs from "node:fs/promises";
import { chromium } from "playwright";

function parseArgs(argv) {
  const options = {
    jobsPath: "",
    outputPath: "",
    userDataDir: "",
    headless: false,
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

async function isLoginRequired(page) {
  const currentUrl = page.url().toLowerCase();
  if (currentUrl.includes("sign_in") || currentUrl.includes("login")) {
    return true;
  }
  const bodyText = normalizeText(await page.locator("body").textContent()).toLowerCase();
  return bodyText.includes("sign in") && bodyText.includes("handshake");
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

async function captureModalState(page) {
  const bodyText = normalizeText(await page.locator("body").textContent());
  return {
    requiresResume: bodyText.includes("Attach your resume") || bodyText.includes("requires a resume"),
    requiresTranscript:
      bodyText.includes("Attach your transcript") || bodyText.includes("requires a transcript"),
    requiresCoverLetter:
      bodyText.includes("Attach your cover letter") || bodyText.includes("requires a cover letter"),
    hasSubmitButton:
      (await page.getByRole("button", { name: /Submit Application/i }).count()) > 0,
    bodyText,
  };
}

async function submitHandshakeJob(page, job) {
  await page.goto(job.url, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(1200);

  if (await isLoginRequired(page)) {
    return {
      job_id: job.id,
      attempted: false,
      submitted: false,
      status: "login_required",
      notes: ["Handshake login is required in the local browser profile before submissions can continue."],
    };
  }

  const externalApply = await clickVisibleButton(page, "Apply externally");
  if (externalApply) {
    return {
      job_id: job.id,
      attempted: false,
      submitted: false,
      status: "external_review_required",
      notes: ["This job redirects externally and should stay in Checkin/Review."],
    };
  }

  const applyClicked = await clickVisibleButton(page, "Apply");
  if (!applyClicked) {
    return {
      job_id: job.id,
      attempted: false,
      submitted: false,
      status: "apply_button_not_found",
      notes: ["Could not find a visible Handshake Apply button on the page."],
    };
  }

  await page.waitForTimeout(1200);
  const modalState = await captureModalState(page);

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

  await page.getByRole("button", { name: /Submit Application/i }).first().click({ force: true, timeout: 5000 });
  await page.waitForTimeout(1600);

  const bodyTextAfter = normalizeText(await page.locator("body").textContent()).toLowerCase();
  const submitStillVisible = (await page.getByRole("button", { name: /Submit Application/i }).count()) > 0;
  const looksSubmitted =
    bodyTextAfter.includes("application submitted") ||
    bodyTextAfter.includes("you applied") ||
    bodyTextAfter.includes("withdraw application");

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
  const options = parseArgs(process.argv.slice(2));
  const jobs = JSON.parse(await fs.readFile(options.jobsPath, "utf8"));
  await fs.mkdir(options.userDataDir, { recursive: true });

  const context = await chromium.launchPersistentContext(options.userDataDir, {
    headless: options.headless,
    viewport: { width: 1440, height: 960 },
  });

  let page = context.pages()[0];
  if (!page) {
    page = await context.newPage();
  }

  const results = [];
  try {
    await page.goto(options.origin, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForTimeout(1200);

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
