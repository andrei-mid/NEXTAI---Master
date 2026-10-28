// This browser's storage, for what the analyst writes before there is an API to save it
// (reviews, messages). Every access can fail (private window, blocked storage): reads then
// fall back and writes are skipped, so the app keeps working for the session.

/** The saved value for key, or fallback when it is missing, unreadable or of another type. */
export function loadStored(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    if (raw === null) return fallback;
    const value = JSON.parse(raw);
    return typeof value === typeof fallback && Array.isArray(value) === Array.isArray(fallback)
      ? value
      : fallback;
  } catch {
    return fallback;
  }
}

export function saveStored(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage unavailable: the data lasts until the tab closes.
  }
}
