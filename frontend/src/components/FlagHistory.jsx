import { REVIEW_OPTIONS } from './ReviewPanel.jsx';
import AnalystName from './AnalystName.jsx';
import { getAnalyst } from '../mock/analysts.js';
import { formatUtc } from '../format.js';

// Reviews with these outcomes are not shown in the flag history.
const HIDDEN = ['no_risk', 'false_positive'];

const LABELS = {
  ...Object.fromEntries(REVIEW_OPTIONS.map((o) => [o.value, o.label])),
  false_positive: 'False positive',
};

/**
 * Closed by default: the analyst opens it only when they want the history.
 * companyName: used in the subject of the e-mail to the analyst who made a review.
 * analystId: the signed-in account (no e-mail link to yourself).
 */
export default function FlagHistory({ entries, companyName, analystId }) {
  const sorted = [...entries].sort((a, b) => b.recorded_at.localeCompare(a.recorded_at));
  const shown = sorted.filter((e) => !HIDDEN.includes(e.choice));
  const hiddenCount = sorted.length - shown.length;

  return (
    <details className="card section-toggle">
      <summary className="card-head">
        <h3>Flag history</h3>
        <span className="sidebar-count">{shown.length}</span>
      </summary>
      <p className="muted small">
        Past reviews that raised a flag. {hiddenCount} review{hiddenCount === 1 ? '' : 's'} marked
        No risk or False positive {hiddenCount === 1 ? 'is' : 'are'} hidden.
      </p>

      {shown.length === 0 ? (
        <p className="muted">No flags raised for this company.</p>
      ) : (
        <ol className="claims">
          {shown.map((e) => {
            const label = LABELS[e.choice] ?? e.choice;
            const who = getAnalyst(e.analyst_id)?.name ?? 'Unknown analyst';
            return (
              <li key={e.recorded_at + e.choice}>
                <details className="claim">
                  <summary>
                    <span className="flag-outcome">{label}</span>
                    <span className="claim-title muted">{who}</span>
                    <span className="claim-date">{e.recorded_at.slice(0, 10)}</span>
                  </summary>
                  <div className="claim-body">
                    <p className="claim-text">{e.comment}</p>
                    <p className="small">
                      <AnalystName
                        id={e.analyst_id}
                        mailSubject={
                          e.analyst_id === analystId
                            ? undefined
                            : `${companyName}: your review "${label}" of ${e.recorded_at.slice(0, 10)}`
                        }
                      />
                      <span className="muted"> · {formatUtc(e.recorded_at)}</span>
                    </p>
                  </div>
                </details>
              </li>
            );
          })}
        </ol>
      )}
    </details>
  );
}
