const TRACKING_SHEET_NAME = 'Applied';
const TRACKING_HEADERS = [
  'Date Applied',
  'Company',
  'Role',
  'Company Description / Role Description',
  'Reply',
  'Status',
  'Job ID',
];
const STATUS_COLUMN = 6;
const JOB_ID_COLUMN = 7;

function doPost(e) {
  try {
    verifySecret_(e);
    const payload = parsePayload_(e);
    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    const sheet = getTrackingSheet_();

    ensureHeaders_(sheet);

    const index = buildJobIndex_(sheet);
    let appended = 0;
    let updated = 0;

    rows.forEach((row) => {
      const jobId = String(row.job_id || '').trim();
      if (!jobId) {
        return;
      }

      const values = buildSheetValues_(row);
      const existingRow = index.get(jobId);
      if (existingRow) {
        sheet.getRange(existingRow, 1, 1, values.length).setValues([values]);
        updated += 1;
      } else {
        sheet.appendRow(values);
        index.set(jobId, sheet.getLastRow());
        updated += 0;
        appended += 1;
      }
    });

    return jsonResponse_({
      ok: true,
      appended,
      updated,
      processed: rows.length,
      sheet: TRACKING_SHEET_NAME,
    });
  } catch (error) {
    return jsonResponse_({
      ok: false,
      error: error && error.message ? error.message : String(error),
    });
  }
}

function verifySecret_(e) {
  const configuredSecret = String(
    PropertiesService.getScriptProperties().getProperty('TRACKING_WEBHOOK_SECRET') || ''
  ).trim();
  if (!configuredSecret) {
    return;
  }

  const providedSecret = String((e && e.parameter && e.parameter.secret) || '').trim();
  if (providedSecret !== configuredSecret) {
    throw new Error('Unauthorized webhook secret.');
  }
}

function parsePayload_(e) {
  if (!e || !e.postData || !e.postData.contents) {
    throw new Error('Missing webhook payload.');
  }
  return JSON.parse(e.postData.contents);
}

function getTrackingSheet_() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = spreadsheet.getSheetByName(TRACKING_SHEET_NAME);
  if (!sheet) {
    throw new Error('Applied sheet not found.');
  }
  return sheet;
}

function ensureHeaders_(sheet) {
  const headerRange = sheet.getRange(1, 1, 1, TRACKING_HEADERS.length);
  const currentHeaders = headerRange.getValues()[0];
  const isMissing = TRACKING_HEADERS.some((header, index) => String(currentHeaders[index] || '').trim() !== header);
  if (isMissing) {
    headerRange.setValues([TRACKING_HEADERS]);
  }
}

function buildJobIndex_(sheet) {
  const lastRow = sheet.getLastRow();
  const index = new Map();
  if (lastRow < 2) {
    return index;
  }

  const values = sheet.getRange(2, JOB_ID_COLUMN, lastRow - 1, 1).getValues();
  values.forEach((row, offset) => {
    const jobId = String(row[0] || '').trim();
    if (jobId && !index.has(jobId)) {
      index.set(jobId, offset + 2);
    }
  });
  return index;
}

function buildSheetValues_(row) {
  const sheetRow = row && row.sheet_row ? row.sheet_row : {};
  return [
    String(sheetRow.A || ''),
    String(sheetRow.B || ''),
    buildHyperlinkFormula_(row.job_url || row.application_url || '', String(sheetRow.C || '')),
    String(sheetRow.D || ''),
    String(sheetRow.E || ''),
    normalizeStatus_(sheetRow.F || row.status || ''),
    String(row.job_id || ''),
  ];
}

function buildHyperlinkFormula_(url, label) {
  const cleanUrl = String(url || '').trim();
  const cleanLabel = String(label || '').trim();
  if (!cleanUrl || !cleanLabel) {
    return cleanLabel;
  }

  const escapedUrl = cleanUrl.replace(/"/g, '""');
  const escapedLabel = cleanLabel.replace(/"/g, '""');
  return `=HYPERLINK("${escapedUrl}","${escapedLabel}")`;
}

function normalizeStatus_(value) {
  const text = String(value || '').trim();
  if (!text) {
    return '';
  }
  const lower = text.toLowerCase();
  if (lower.includes('applied')) {
    return 'applied';
  }
  if (lower.includes('checkin/review')) {
    return 'Checkin/Review';
  }
  if (lower.includes('queued')) {
    return 'queued';
  }
  return text;
}

function jsonResponse_(payload) {
  return ContentService.createTextOutput(JSON.stringify(payload)).setMimeType(
    ContentService.MimeType.JSON
  );
}
