/**
 * One bar per component, drawn from the list the API sends (not a fixed list of 8),
 * so a new agent shows up without code changes. Scores are shown exactly as received.
 * An unavailable component is a grey bar, never a clean one.
 */
export default function ComponentBars({ components }) {
  return (
    <section className="card">
      <h3>Components</h3>
      {components.length === 0 ? (
        <p className="muted">Not checked yet: no component results. This is not a clean result.</p>
      ) : (
        <ul className="bars">
          {components.map((c) => {
            const n = c.signal_ids?.length ?? 0;
            return (
              <li key={c.component} className={c.available ? '' : 'bar-unavailable'}>
                <span className="bar-name">{c.component}</span>
                <span className="bar-track" aria-hidden="true">
                  {c.available && c.score != null && (
                    <span className="bar-fill" style={{ width: `${c.score}%` }} />
                  )}
                </span>
                <span className="bar-value">{c.available ? (c.score ?? '—') : c.status}</span>
                <span className="muted small bar-meta">
                  {c.available
                    ? `${n} signal${n === 1 ? '' : 's'} · weight ${c.weight}${
                        c.status === 'partial' ? ' · partial check' : ''
                      }`
                    : `Source ${c.status}. Not checked, so not a clean result.`}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
