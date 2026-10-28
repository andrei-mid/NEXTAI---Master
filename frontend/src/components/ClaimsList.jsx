import SourceLink from './SourceLink.jsx';

export default function ClaimsList({ claims }) {
  const unsourced = claims.filter((c) => !c.source?.url).length;

  return (
    <section className="card">
      <div className="card-head">
        <h3>Claims and sources</h3>
        <span className="sidebar-count">{claims.length}</span>
        {unsourced > 0 && (
          <span className="pill pill-expired">
            {unsourced} without source
          </span>
        )}
      </div>
      <p className="muted small">Every claim links to the source that supports it. Open it to check.</p>

      <ul className="claims">
        {claims.map((c) => (
          <li key={c.rule_id + c.claim} className={c.source?.url ? '' : 'claim-unsourced'}>
            <div className="claim-head">
              <span className={`pill sev-${c.severity}`}>{c.severity}</span>
              {c.source?.type === 'mock' && <span className="pill pill-mock">MOCK</span>}
              {!c.validated && <span className="pill pill-unvalidated">unvalidated</span>}
              <span className="muted small">{c.rule_id}</span>
            </div>
            <p className="claim-text">{c.claim}</p>
            <SourceLink source={c.source} evidenceDate={c.evidence_date} />
          </li>
        ))}
      </ul>
    </section>
  );
}
