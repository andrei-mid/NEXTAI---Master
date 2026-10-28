const ronFormat = new Intl.NumberFormat('ro-RO', { maximumFractionDigits: 0 });

/** 1250000 -> "1.250.000 RON" */
export function formatRon(value) {
  return `${ronFormat.format(value)} RON`;
}

/** "2026-10-28T09:00:00Z" -> "2026-10-28 09:00 UTC". null -> "unknown" */
export function formatUtc(iso) {
  if (!iso) return 'unknown';
  return `${iso.slice(0, 16).replace('T', ' ')} UTC`;
}

/** Whole days from today until a "YYYY-MM-DD" date (negative if in the past). */
export function daysUntil(date) {
  const target = new Date(`${date}T00:00:00Z`).getTime();
  const today = new Date(new Date().toISOString().slice(0, 10) + 'T00:00:00Z').getTime();
  return Math.round((target - today) / 86_400_000);
}

// CompanyStatus values from verifirm/schema/identity.py. Unknown values are shown as-is.
const STATUS_LABELS = {
  active: 'Active',
  inactive_anaf: 'Inactive (ANAF)',
  suspended: 'Suspended',
  in_dissolution: 'In dissolution',
  insolvency: 'Insolvency',
  bankruptcy: 'Bankruptcy',
  deregistered: 'Deregistered',
  unknown: 'Unknown',
};

export function statusLabel(status) {
  return STATUS_LABELS[status] ?? status ?? 'Unknown';
}

/** Coverage from the API: "7/8 sources (85%)", or a clear "not checked" text when missing. */
export function coverageLabel(coverage) {
  if (!coverage) return 'not checked yet';
  return `${coverage.available}/${coverage.total} sources (${coverage.weight_pct}%)`;
}
