/**
 * One bar per component, drawn from the list the API sends (not a fixed list of 8),
 * so a new agent shows up without code changes. Scores are shown exactly as received.
 * An unavailable component is a grey bar, never a clean one.
 */
export default function ComponentBars({ components, sources }) {
  const notes = Object.fromEntries((sources ?? []).map((s) => [s.component, s]));

  return (
    <section className="card">
      <h3>Components</h3>
      <ul className="bars">
        {components.map((c) => (
          <li key={c.component} className={c.available ? '' : 'bar-unavailable'}>
            <span className="bar-name">{c.component}</span>
            <span className="bar-track" aria-hidden="true">
              {c.available && c.score !== null && <span className="bar-fill" style={{ width: `${c.score}%` }} />}
            </span>
            <span className="bar-value">
              {c.available ? (c.score ?? '—') : 'unavailable'}
            </span>
            <span className="muted small bar-meta">
              {c.available
                ? `${c.n_signals} signal${c.n_signals === 1 ? '' : 's'} · weight ${c.weight}`
                : notes[c.component]?.notes ?? 'Not checked. Not a clean result.'}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
