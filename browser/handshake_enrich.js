import fs from "node:fs/promises";

function normalizeText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

async function extractPageSummary(tab) {
  return tab.playwright.evaluate(() => {
    function text(value) {
      return String(value || "").replace(/\s+/g, " ").trim();
    }

    const main = document.querySelector("main");
    const title = text(main?.querySelector("h1")?.textContent);
    const companyLinks = Array.from(main?.querySelectorAll('a[href*="/e/"]') || []);
    const company = text(companyLinks[1]?.textContent || companyLinks[0]?.textContent);

    const applyButtons = Array.from(main?.querySelectorAll("button") || [])
      .map((button) => text(button.getAttribute("aria-label") || button.textContent))
      .filter(Boolean);

    const paragraphTexts = Array.from(main?.querySelectorAll("p") || [])
      .map((node) => text(node.textContent))
      .filter(Boolean);

    const description = paragraphTexts.slice(0, 6).join(" ").slice(0, 1500);

    return {
      title,
      company,
      description,
      applyButtons,
      pageText: text(main?.textContent).slice(0, 3000),
    };
  });
}

async function inspectApplicationModal(tab, applicationMethod) {
  const modal = {
    requires_resume: false,
    requires_transcript: false,
    requires_cover_letter: false,
    modal_step: "",
  };

  const buttonName = applicationMethod === "external" ? "Apply externally" : "Apply";
  const buttons = tab.playwright.getByRole("button", { name: buttonName });
  const count = await buttons.count();
  if (count < 1) {
    return modal;
  }

  let clicked = false;
  for (let index = 0; index < count; index += 1) {
    const candidate = buttons.nth(index);
    if (await candidate.isVisible()) {
      await candidate.click({ force: true, timeoutMs: 3000 });
      clicked = true;
      break;
    }
  }
  if (!clicked) {
    return modal;
  }
  await tab.playwright.waitForTimeout(1200);

  const modalSnapshot = await tab.playwright.domSnapshot();
  modal.requires_resume =
    modalSnapshot.includes("Attach your resume") || modalSnapshot.includes("requires a resume");
  modal.requires_transcript =
    modalSnapshot.includes("Attach your transcript") || modalSnapshot.includes("requires a transcript");
  modal.requires_cover_letter =
    modalSnapshot.includes("Attach your cover letter") || modalSnapshot.includes("requires a cover letter");

  if (modalSnapshot.includes('dialog "Apply to')) {
    modal.modal_step = "Apply to employer";
  }
  if (modalSnapshot.includes('dialog "Step 1: Submit Documents on Handshake"')) {
    modal.modal_step = "Step 1: Submit Documents on Handshake";
  }

  const cancel = tab.playwright.getByRole("button", { name: "Cancel application" });
  if ((await cancel.count()) >= 1) {
    await cancel.click({});
    await tab.playwright.waitForTimeout(400);
  }

  return modal;
}

export async function enrichHandshakeJobs(
  tab,
  jobs,
  {
    limit = 10,
    outputPath = "",
  } = {},
) {
  const enriched = [];

  for (const job of jobs.slice(0, limit)) {
    await tab.goto(job.url);
    await tab.playwright.waitForLoadState({ state: "domcontentloaded", timeoutMs: 30000 });
    await tab.playwright.waitForTimeout(1200);

    const summary = await extractPageSummary(tab);
    const buttonLabels = summary.applyButtons.map((label) => normalizeText(label).toLowerCase());
    const applicationMethod = buttonLabels.includes("apply externally")
      ? "external"
      : buttonLabels.includes("apply")
        ? "internal"
        : "unknown";

    const modal = applicationMethod === "unknown" ? {
      requires_resume: job.requires_resume,
      requires_transcript: job.requires_transcript,
      requires_cover_letter: job.requires_cover_letter,
      modal_step: "",
    } : await inspectApplicationModal(tab, applicationMethod);

    enriched.push({
      ...job,
      title: summary.title || job.title,
      company: summary.company || job.company,
      description: summary.description || job.description,
      application_method: applicationMethod,
      application_url: job.url,
      requires_resume: modal.requires_resume || job.requires_resume,
      requires_transcript: modal.requires_transcript || false,
      requires_cover_letter: modal.requires_cover_letter || false,
      detail_modal_step: modal.modal_step,
    });
  }

  if (outputPath) {
    await fs.writeFile(outputPath, `${JSON.stringify(enriched, null, 2)}\n`, "utf8");
  }

  return enriched;
}
