import SourceLink from './SourceLink.jsx';
import { formatUtc } from '../format.js';

/** Signals from GET /companies/{cui}/signals. null = no data yet (404). */
export default function ClaimsList({ claims, lastChecked }) {
  const unsourced = (claims ?? []).filter((c) => !c.source?.url).length;

  return (
    <section className="card">
      <div className="card-head">
        <h3>Claims and sources</h3>
        {claims && <span className="sidebar-count">{claims.length}</span>}
        {unsourced > 0 && <span className="pill pill-expired">{unsourced} without source link</span>}
      </div>
      <p className="muted small">Every claim links to the source that supports it. Open it to check.</p>

      {claims === null && (
        <p className="muted">Not checked yet: no signals available for this company.</p>
      )}
      {claims?.length === 0 && (
        <p className="muted">No signals found in the checked sources as of {formatUtc(lastChecked)}.</p>
      )}

      {claims?.length > 0 && (
        <ul className="claims">
          {claims.map((c) => (
            <li key={c.signal_id} className={c.source?.url ? '' : 'claim-unsourced'}>
              <div className="claim-head">
                <span className={`pill sev-${c.severity}`}>{c.severity}</span>
                {c.source?.type === 'mock' && <span className="pill pill-mock">MOCK</span>}
                {!c.validated && <span className="pill pill-unvalidated">unvalidated</span>}
                {c.auto_stop_candidate && <span className="pill band-stop">auto-stop</span>}
                <span className="muted small">
                  {c.component} · {c.rule_id}
                </span>
              </div>
              <p className="claim-text">{c.claim}</p>
              <SourceLink source={c.source} evidenceDate={c.evidence_date} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
