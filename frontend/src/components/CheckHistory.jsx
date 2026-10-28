import BandBadge from './BandBadge.jsx';
import { coverageLabel, formatUtc } from '../format.js';

/**
 * Every check the backend ran on this company (GET /history `scores`), newest first.
 * history: undefined while loading, null when there is none or it failed.
 */
export default function CheckHistory({ history }) {
  const loading = history === undefined;
  const runs = [...(history?.scores ?? [])].reverse();

  return (
    <section className="card">
      <div className="card-head">
        <h3>Check history</h3>
        {runs.length > 0 && <span className="sidebar-count">{runs.length}</span>}
      </div>
      <p className="muted small">Each automatic check of this company and what it found.</p>
      {loading ? (
        <p className="muted">Loading check history from the server…</p>
      ) : history === null ? (
        <p className="muted">Check history could not be loaded right now.</p>
      ) : runs.length === 0 ? (
        <p className="muted">No earlier checks recorded.</p>
      ) : (
        <ol className="check-history">
          {runs.map((r) => (
            <li key={r.run_id}>
              <span className="check-date">{formatUtc(r.computed_at)}</span>
              <BandBadge band={r.band} />
              <span className="muted small">
                score {r.score ?? '—'} · {coverageLabel(r.coverage)}
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
