import { REVIEW_OPTIONS } from './ReviewPanel.jsx';
import { formatUtc } from '../format.js';

// Reviews with these outcomes are not shown in the flag history.
const HIDDEN = ['no_risk', 'false_positive'];

const LABELS = {
  ...Object.fromEntries(REVIEW_OPTIONS.map((o) => [o.value, o.label])),
  false_positive: 'False positive',
};

export default function FlagHistory({ entries }) {
  const sorted = [...entries].sort((a, b) => b.recorded_at.localeCompare(a.recorded_at));
  const shown = sorted.filter((e) => !HIDDEN.includes(e.choice));
  const hiddenCount = sorted.length - shown.length;

  return (
    <section className="card">
      <div className="card-head">
        <h3>Flag history</h3>
        <span className="pill pill-mock">MOCK</span>
        <span className="pill pill-proposal">not in API contract</span>
      </div>
      <p className="muted small">
        Past reviews that raised a flag. {hiddenCount} review{hiddenCount === 1 ? '' : 's'} marked
        No risk or False positive {hiddenCount === 1 ? 'is' : 'are'} hidden.
      </p>

      {shown.length === 0 ? (
        <p className="muted">No flags raised for this company.</p>
      ) : (
        <ol className="timeline">
          {shown.map((e) => (
            <li key={e.recorded_at + e.choice}>
              <div className="timeline-head">
                <span className="pill pill-outcome">{LABELS[e.choice] ?? e.choice}</span>
                <span className="muted small">
                  {formatUtc(e.recorded_at)} · {e.analyst ?? 'You (this session)'}
                </span>
              </div>
              <p>{e.comment}</p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
