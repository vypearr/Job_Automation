import fs from "node:fs/promises";

export async function collectHandshakeSearchJobs(
  tab,
  {
    origin = "https://sfsu.joinhandshake.com",
    startPage = 1,
    pages = 3,
    perPage = 25,
    outputPath = "",
  } = {},
) {
  const collected = [];
  const seen = new Set();

  for (let offset = 0; offset < pages; offset += 1) {
    const page = startPage + offset;
    const url = `${origin}/job-search?page=${page}&per_page=${perPage}`;
    await tab.goto(url);
    await tab.playwright.waitForLoadState({ state: "domcontentloaded", timeoutMs: 30000 });
    await tab.playwright.waitForTimeout(1200);

    const jobs = await tab.playwright.evaluate(({ origin, page, perPage }) => {
      function normalizeText(value) {
        return String(value || "").replace(/\s+/g, " ").trim();
      }

      function buildSyntheticDescription(card) {
        const parts = [
          "Imported from live Handshake search results.",
          `Company: ${card.company}.`,
          `Title: ${card.title}.`,
        ];

        if (card.compensation) {
          parts.push(`Compensation: ${card.compensation}.`);
        }
        if (card.employmentType) {
          parts.push(`Type: ${card.employmentType}.`);
        }
        if (card.location) {
          parts.push(`Location: ${card.location}.`);
        }
        if (card.postedRelative) {
          parts.push(`Posted: ${card.postedRelative}.`);
        }

        return parts.join(" ");
      }

      function isPostedMarker(text) {
        return /^(new|\d+\s?(?:h|d|wk|wks|mo|mos|yr|yrs)\s+ago|\d+\s?(?:h|d|wk|wks|mo|mos|yr|yrs)|today)$/i.test(
          text,
        );
      }

      const jobsList = Array.from(document.querySelectorAll('[role="region"]')).find(
        (el) => (el.getAttribute("aria-label") || "").includes("Jobs List"),
      );
      if (!jobsList) {
        return [];
      }

      const cardWrappers = Array.from(jobsList.querySelectorAll('[data-hook^="job-result-card | "]'));
      return cardWrappers
        .map((wrapper, index) => {
          const jobId = normalizeText((wrapper.getAttribute("data-hook") || "").split("|")[1]);
          const cardRegion = wrapper.querySelector('[role="region"]');
          const company = normalizeText(cardRegion?.querySelector("span")?.textContent);
          const titleNode = cardRegion?.querySelector("[id][aria-label]");
          const title = normalizeText(titleNode?.textContent);
          const detailBits = Array.from(
            cardRegion?.querySelectorAll('[data-hook="job-result-card-footer"] span') || [],
          )
            .map((node) => normalizeText(node.textContent))
            .filter(Boolean)
            .filter((text) => text !== "∙")
            .filter((text) => text !== "Promoted")
            .filter((text) => text !== "SFSU collection");

          const metaNode = cardRegion?.querySelector('[class*="gCaTWI"]');
          const metaParts = normalizeText(metaNode?.textContent)
            .split("·")
            .map((part) => normalizeText(part))
            .filter(Boolean);

          const postedRelative =
            detailBits.length > 0 && isPostedMarker(detailBits[detailBits.length - 1])
              ? detailBits[detailBits.length - 1]
              : "";
          const locationParts = postedRelative ? detailBits.slice(0, -1) : detailBits;
          const location = locationParts.join(" · ");
          const compensation = metaParts[0] || "";
          const employmentType = metaParts.slice(1).join(" · ");
          const jobUrl = jobId
            ? `${origin}/jobs/${jobId}`
            : `${origin}/job-search?page=${page}&per_page=${perPage}`;

          if (!company || !title) {
            return null;
          }

          return {
            id: jobId ? `handshake-${jobId}` : `handshake-page-${page}-card-${index + 1}`,
            title,
            company,
            location,
            url: jobUrl,
            description: buildSyntheticDescription({
              company,
              title,
              location,
              compensation,
              employmentType,
              postedRelative,
            }),
            source: "handshake_live_search",
            application_method: "unknown",
            application_url: jobUrl,
            requires_cover_letter: false,
            requires_transcript: false,
            requires_resume: true,
            posted_relative: postedRelative,
            visible_page: page,
          };
        })
        .filter(Boolean);
    }, { origin, page, perPage });
    for (const job of jobs) {
      if (seen.has(job.id)) {
        continue;
      }
      seen.add(job.id);
      collected.push(job);
    }
  }

  if (outputPath) {
    await fs.writeFile(outputPath, `${JSON.stringify(collected, null, 2)}\n`, "utf8");
  }

  return collected;
}
