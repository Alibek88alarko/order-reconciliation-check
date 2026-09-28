/**
 * Pull a BigQuery query into a Google Sheet tab, with a "Last refreshed" cell business users can trust.
 * Apps Script: Extensions > Apps Script, enable the BigQuery advanced service (Services > BigQuery API),
 * then run refreshDailyTotals() manually once to grant access, and add a time-driven trigger (e.g. every hour).
 */
const PROJECT_ID = 'your-gcp-project';
const TAB_NAME = 'daily_totals';
const QUERY = `
  SELECT order_date, COUNT(*) AS orders, ROUND(SUM(total), 2) AS revenue_eur
  FROM \`your-gcp-project.reporting.orders\`
  WHERE order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
  GROUP BY order_date
  ORDER BY order_date`;

function refreshDailyTotals() {
  const request = { query: QUERY, useLegacySql: false };
  let result = BigQuery.Jobs.query(request, PROJECT_ID);
  const jobId = result.jobReference.jobId;
  while (!result.jobComplete) {                 // large queries finish asynchronously
    Utilities.sleep(500);
    result = BigQuery.Jobs.getQueryResults(PROJECT_ID, jobId);
  }
  const header = result.schema.fields.map(f => f.name);
  const rows = (result.rows || []).map(r => r.f.map(c => c.v));

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(TAB_NAME) || ss.insertSheet(TAB_NAME);
  sheet.clearContents();
  sheet.getRange(1, 1).setValue('Last refreshed: ' + Utilities.formatDate(new Date(), ss.getSpreadsheetTimeZone(), 'yyyy-MM-dd HH:mm'));
  sheet.getRange(2, 1, 1, header.length).setValues([header]).setFontWeight('bold');
  if (rows.length) {
    sheet.getRange(3, 1, rows.length, header.length).setValues(rows);
  }
  sheet.setFrozenRows(2);
  // total row so the number people quote is the one on the sheet, not one they add by hand
  const last = 2 + rows.length;
  sheet.getRange(last + 1, 1).setValue('TOTAL');
  sheet.getRange(last + 1, 2).setFormula(`=SUM(B3:B${last})`);
  sheet.getRange(last + 1, 3).setFormula(`=SUM(C3:C${last})`);
}
