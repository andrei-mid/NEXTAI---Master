import { useState } from 'react';
import SourceLink from './SourceLink.jsx';
import CheckedSources from './CheckedSources.jsx';
import { coverageLabel, formatUtc } from '../format.js';
import { severityRank } from '../severity.js';

// "Date found": the evidence date when the source gives one, else when we retrieved it.
function foundDate(c) {
  return c.evidence_date ?? c.source?.retrieved_at?.slice(0, 10) ?? '';
}

const SORTS = {
  importance: {
    label: 'Importance',
    compare: (a, b) =>
      severityRank(a.severity) - severityRank(b.severity) || foundDate(b).localeCompare(foundDate(a)),
  },
  date: {
    label: 'Date found',
    compare: (a, b) =>
      foundDate(b).localeCompare(foundDate(a)) || severityRank(a.severity) - severityRank(b.severity),
  },
};

function componentLabel(component) {
  return component ? component.charAt(0).toUpperCase() + component.slice(1) : 'Other';
}

/** Signals from GET /companies/{cui}/signals. null = no data yet (404). Collapsed rows; click to open. */
export default function ClaimsList({ claims, lastChecked, coverage, company }) {
  const [sort, setSort] = useState('importance');
  const unsourced = (claims ?? []).filter((c) => !c.source?.url).length;
  const sorted = claims ? [...claims].sort(SORTS[sort].compare) : null;

  return (
    <section className="card">
      <div className="card-head">
        <h3>Claims and sources</h3>
        {claims && <span className="sidebar-count">{claims.length}</span>}
        {unsourced > 0 && <span className="pill pill-expired">{unsourced} without source link</span>}
        {claims?.length > 1 && (
          <div className="segmented" role="group" aria-label="Sort claims by">
            {Object.entries(SORTS).map(([key, s]) => (
              <button
                key={key}
                type="button"
                className={sort === key ? 'is-active' : undefined}
                aria-pressed={sort === key}
                onClick={() => setSort(key)}
              >
                {s.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {claims === null && (
        <p className="muted">Not checked yet: no signals available for this company.</p>
      )}
      {claims?.length === 0 && (
        <>
          <p className="muted">
            No signals found as of {formatUtc(lastChecked)}.
            {coverage && <> Checked: {coverageLabel(coverage)}.</>}
          </p>
          {company && <CheckedSources company={company} />}
        </>
      )}

      {sorted?.length > 0 && (
        <ul className="claims">
          {sorted.map((c) => {
            const sourced = Boolean(c.source?.url);
            return (
              <li key={c.signal_id}>
                <details
                  className={`claim${sourced ? '' : ' claim-unsourced'}`}
                  style={{ borderLeftColor: `var(--sev-${c.severity}, var(--sev-info))` }}
                  onToggle={(e) => {
                    // Keep an opened claim fully visible inside the scroll box.
                    const el = e.currentTarget;
                    if (el.open) requestAnimationFrame(() => el.scrollIntoView({ block: 'nearest' }));
                  }}
                >
                  <summary>
                    <span className="claim-component">{componentLabel(c.component)}</span>
                    <span className="claim-title">{c.claim}</span>
                    {!sourced && (
                      <span className="pill pill-expired pill-xs" title="No source link">
                        no source
                      </span>
                    )}
                    <span className="claim-date">{foundDate(c) || '—'}</span>
                  </summary>

                  <div className="claim-body">
                    <p className="claim-text">{c.claim}</p>
                    <div className="claim-head">
                      <span className={`pill sev-${c.severity}`}>{c.severity}</span>
                      {c.source?.type === 'mock' && <span className="pill pill-mock">MOCK</span>}
                      {!c.validated && <span className="pill pill-unvalidated">unvalidated</span>}
                      {c.auto_stop_candidate && <span className="pill band-stop">auto-stop</span>}
                      <span className="muted small">{c.rule_id}</span>
                    </div>
                    <SourceLink source={c.source} evidenceDate={c.evidence_date} />
                  </div>
                </details>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
