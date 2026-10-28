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

const nameOf = (id) => getAnalyst(id)?.name ?? 'Unknown analyst';

/** One collapsed row; the body opens on click. */
function Row({ outcome, who, date, children }) {
  return (
    <li>
      <details className="claim">
        <summary>
          <span className="flag-outcome">{outcome}</span>
          <span className="claim-title muted">{who}</span>
          <span className="claim-date">{date.slice(0, 10)}</span>
        </summary>
        <div className="claim-body">{children}</div>
      </details>
    </li>
  );
}

/**
 * Reviews that raised a flag plus the messages sent about this company, newest first.
 * Closed by default: the analyst opens it only when they want the history.
 * companyName: used in the subject of the e-mail to the analyst who made a review.
 * analystId: the signed-in account (no e-mail link to yourself).
 */
export default function FlagHistory({ entries, messages = [], cui, companyName, analystId }) {
  const flags = entries.filter((e) => !HIDDEN.includes(e.choice));
  const hiddenCount = entries.length - flags.length;
  const alert = { cui, name: companyName };

  const rows = [
    ...flags.map((e) => ({ kind: 'review', at: e.recorded_at, e })),
    ...messages.map((m) => ({ kind: 'message', at: m.sent_at, m })),
  ].sort((a, b) => b.at.localeCompare(a.at));

  return (
    <details className="card section-toggle">
      <summary className="card-head">
        <h3>Flag history</h3>
        <span className="sidebar-count">{rows.length}</span>
      </summary>
      <p className="muted small">
        Past reviews that raised a flag, and messages about this company. {hiddenCount} review
        {hiddenCount === 1 ? '' : 's'} marked No risk or False positive{' '}
        {hiddenCount === 1 ? 'is' : 'are'} hidden.
      </p>

      {rows.length === 0 ? (
        <p className="muted">No flags or messages for this company.</p>
      ) : (
        <ol className="claims">
          {rows.map((row) => {
            if (row.kind === 'message') {
              const { m } = row;
              return (
                <Row
                  key={`m-${m.id}`}
                  outcome="Message"
                  who={`${nameOf(m.from)} → ${nameOf(m.to)}`}
                  date={m.sent_at}
                >
                  <p className="claim-text">{m.text}</p>
                  <p className="small">
                    <AnalystName id={m.from} alert={alert} />
                    <span className="muted"> → </span>
                    <AnalystName id={m.to} alert={alert} />
                    <span className="muted"> · {formatUtc(m.sent_at)}</span>
                  </p>
                </Row>
              );
            }
            const { e } = row;
            const label = LABELS[e.choice] ?? e.choice;
            return (
              <Row
                key={`r-${e.recorded_at}-${e.choice}`}
                outcome={label}
                who={nameOf(e.analyst_id)}
                date={e.recorded_at}
              >
                <p className="claim-text">{e.comment}</p>
                <p className="small">
                  <AnalystName
                    id={e.analyst_id}
                    alert={alert}
                    mailSubject={
                      e.analyst_id === analystId
                        ? undefined
                        : `${companyName}: your review "${label}" of ${e.recorded_at.slice(0, 10)}`
                    }
                  />
                  <span className="muted"> · {formatUtc(e.recorded_at)}</span>
                </p>
              </Row>
            );
          })}
        </ol>
      )}
    </details>
  );
}
