const ronFormat = new Intl.NumberFormat('ro-RO', { maximumFractionDigits: 0 });

/** 1250000 -> "1.250.000 RON" */
export function formatRon(value) {
  return `${ronFormat.format(value)} RON`;
}

/** "2026-10-28T09:00:00Z" -> "2026-10-28 09:00 UTC" */
export function formatUtc(iso) {
  return `${iso.slice(0, 16).replace('T', ' ')} UTC`;
}

/** Whole days from today until a "YYYY-MM-DD" date (negative if in the past). */
export function daysUntil(date) {
  const target = new Date(`${date}T00:00:00Z`).getTime();
  const today = new Date(new Date().toISOString().slice(0, 10) + 'T00:00:00Z').getTime();
  return Math.round((target - today) / 86_400_000);
}
