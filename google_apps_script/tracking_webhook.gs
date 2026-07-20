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
    dedupeSheetByJobId_(sheet);

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
        writeSheetRow_(sheet, existingRow, values, row);
        updated += 1;
      } else {
        const newRow = sheet.getLastRow() + 1;
        writeSheetRow_(sheet, newRow, values, row);
        index.set(jobId, newRow);
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

function dedupeSheetByJobId_(sheet) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 3) {
    return;
  }

  const values = sheet.getRange(2, 1, lastRow - 1, TRACKING_HEADERS.length).getValues();
  const firstSeenRowByJobId = new Map();
  const duplicateRows = [];

  values.forEach((row, offset) => {
    const jobId = String(row[JOB_ID_COLUMN - 1] || '').trim();
    if (!jobId) {
      return;
    }
    const sheetRowNumber = offset + 2;
    if (firstSeenRowByJobId.has(jobId)) {
      duplicateRows.push(sheetRowNumber);
      return;
    }
    firstSeenRowByJobId.set(jobId, sheetRowNumber);
  });

  duplicateRows
    .sort((a, b) => b - a)
    .forEach((rowNumber) => {
      sheet.deleteRow(rowNumber);
    });
}

function buildSheetValues_(row) {
  const sheetRow = row && row.sheet_row ? row.sheet_row : {};
  return [
    String(sheetRow.A || ''),
    String(sheetRow.B || ''),
    String(sheetRow.C || ''),
    String(sheetRow.D || ''),
    String(sheetRow.E || ''),
    normalizeStatus_(sheetRow.F || row.status || ''),
    String(row.job_id || ''),
  ];
}

function writeSheetRow_(sheet, rowNumber, values, row) {
  const existingValues = sheet.getRange(rowNumber, 1, 1, values.length).getDisplayValues()[0];
  const mergedValues = mergeStickyAppliedValues_(existingValues, values);
  sheet.getRange(rowNumber, 1, 1, mergedValues.length).setValues([mergedValues]);

  const hyperlinkFormula = buildHyperlinkFormula_(
    row && (row.job_url || row.application_url || ''),
    mergedValues[2]
  );
  const roleCell = sheet.getRange(rowNumber, 3);
  if (hyperlinkFormula) {
    roleCell.setFormula(hyperlinkFormula);
  } else {
    roleCell.setValue(mergedValues[2]);
  }
}

function mergeStickyAppliedValues_(existingValues, incomingValues) {
  const merged = incomingValues.slice();
  const existingStatus = normalizeStatus_(existingValues[STATUS_COLUMN - 1] || '');
  const incomingStatus = normalizeStatus_(incomingValues[STATUS_COLUMN - 1] || '');

  // Once a job is marked applied in the sheet, later webhook syncs should not
  // regress it back to queued or review because cloud/local state may lag.
  if (existingStatus === 'applied' && incomingStatus !== 'applied') {
    merged[STATUS_COLUMN - 1] = 'applied';
    if (String(existingValues[0] || '').trim()) {
      merged[0] = String(existingValues[0] || '').trim();
    }
  }

  return merged;
}

function buildHyperlinkFormula_(url, label) {
  const cleanUrl = String(url || '').trim();
  const cleanLabel = String(label || '').trim();
  if (!cleanUrl || !cleanLabel) {
    return '';
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
