import { formatUtc } from '../format.js';

/**
 * What a check covered, from GET /companies/{cui}: the components that ran, the ones that
 * did not, and the cited sources (links). Used where a result needs its basis shown,
 * e.g. an inconclusive band or "no signals found".
 */
export default function CheckedSources({ company }) {
  const checked = company.components.filter((c) => c.available).map((c) => c.component);
  const missing = company.components.filter((c) => !c.available).map((c) => c.component);
  const sources = company.sources ?? [];

  return (
    <dl className="checked-sources">
      <div>
        <dt>Checked</dt>
        <dd>{checked.length ? checked.join(', ') : 'nothing yet'}</dd>
      </div>
      {missing.length > 0 && (
        <div>
          <dt>Not checked yet</dt>
          <dd>{missing.join(', ')}</dd>
        </div>
      )}
      <div>
        <dt>Sources cited</dt>
        <dd>
          {sources.length === 0 ? (
            <span className="source-missing-inline">No source cited by the API.</span>
          ) : (
            sources.map((s, i) => (
              <span key={s.name + s.retrieved_at}>
                {i > 0 && ' · '}
                {s.url ? (
                  <a href={s.url} target="_blank" rel="noopener noreferrer">
                    {s.name} ↗
                  </a>
                ) : (
                  <span className="source-missing-inline">{s.name} (no link)</span>
                )}
                <span className="muted small"> data as of {formatUtc(s.retrieved_at)}</span>
              </span>
            ))
          )}
        </dd>
      </div>
    </dl>
  );
}
