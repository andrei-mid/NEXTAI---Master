import { useState } from 'react';
import { formatUtc } from '../format.js';
import AnalystName from './AnalystName.jsx';

// The analyst's own judgement. All options look the same: the UI never suggests one.
export const REVIEW_OPTIONS = [
  { value: 'no_risk', label: 'No risk' },
  { value: 'registry_mismatch', label: 'Status differs between registries' },
  { value: 'escalate', label: 'Escalate' },
  { value: 'unreliable_data', label: 'Unreliable data' },
];

const labelOf = (value) => REVIEW_OPTIONS.find((o) => o.value === value)?.label ?? value;

/** analystId: the signed-in account; every recorded review is attributed to it. */
export default function ReviewPanel({ company, analystId, history, onSubmit }) {
  const [choice, setChoice] = useState(null);
  const [comment, setComment] = useState('');
  const canSubmit = choice !== null && comment.trim().length > 0;

  function handleSubmit(event) {
    event.preventDefault();
    if (!canSubmit) return;
    onSubmit({
      choice,
      comment: comment.trim(),
      analyst_id: analystId,
      recorded_at: new Date().toISOString(),
    });
    setChoice(null);
    setComment('');
  }

  return (
    <aside className="review-panel" aria-label="Analyst review">
      <h2 className="sidebar-title">Your review</h2>
      <p className="review-company">{company.name}</p>
      <p className="muted small review-as">
        Recorded as <AnalystName id={analystId} />
      </p>

      <form onSubmit={handleSubmit}>
        <fieldset className="review-options">
          <legend className="review-label">Assessment</legend>
          {REVIEW_OPTIONS.map((option) => (
            <label
              key={option.value}
              className={`review-option${choice === option.value ? ' is-checked' : ''}`}
            >
              <input
                type="radio"
                name="review"
                value={option.value}
                checked={choice === option.value}
                onChange={() => setChoice(option.value)}
              />
              {option.label}
            </label>
          ))}
        </fieldset>

        <label className="review-label" htmlFor="review-comment">
          Comment <span className="muted">(required)</span>
        </label>
        <textarea
          id="review-comment"
          className="review-comment"
          rows={5}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Why did you choose this? What did you check?"
        />

        <button type="submit" className="btn btn-primary review-submit" disabled={!canSubmit}>
          Record review
        </button>
        {!canSubmit && (
          <p className="review-hint muted">Pick an assessment and write a comment to record it.</p>
        )}
      </form>

      <h3 className="review-label review-history-title">History for this company</h3>
      {history.length === 0 ? (
        <p className="muted review-hint">No reviews recorded yet.</p>
      ) : (
        <ul className="review-history">
          {[...history].reverse().map((r) => (
            <li key={r.recorded_at}>
              <strong>{labelOf(r.choice)}</strong>
              <span className="muted"> · {formatUtc(r.recorded_at)}</span>
              <div className="small">
                <AnalystName
                  id={r.analyst_id}
                  alert={{ cui: company.cui, name: company.name }}
                  mailSubject={
                    r.analyst_id === analystId
                      ? undefined
                      : `${company.name}: your review "${labelOf(r.choice)}" of ${r.recorded_at.slice(0, 10)}`
                  }
                />
              </div>
              <p>{r.comment}</p>
            </li>
          ))}
        </ul>
      )}
      <p className="review-hint muted">Saved in this browser only. Not sent anywhere yet.</p>
    </aside>
  );
}
