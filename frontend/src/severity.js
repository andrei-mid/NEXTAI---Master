// Display order only: severity comes from the API as-is, we never re-score it.
const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low', 'info'];

/** Position in the order; unknown values go last so a new value never jumps to the top. */
export function severityRank(severity) {
  const i = SEVERITY_ORDER.indexOf(severity);
  return i === -1 ? SEVERITY_ORDER.length : i;
}

/** Signals sorted most severe first. */
export function sortSignals(signals) {
  return [...signals].sort((a, b) => severityRank(a.severity) - severityRank(b.severity));
}

/** Portfolio items sorted by their top signal, then most recently checked first. */
export function sortByCriticality(items) {
  return [...items].sort(
    (a, b) =>
      severityRank(a.top_signal?.severity) - severityRank(b.top_signal?.severity) ||
      (b.last_checked ?? '').localeCompare(a.last_checked ?? ''),
  );
}
