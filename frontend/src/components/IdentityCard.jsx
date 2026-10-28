import BandBadge from './BandBadge.jsx';

/** Header of the company page: identity_sheet + score + coverage from GET /companies/{cui}. */
export default function IdentityCard({ company }) {
  const id = company.identity_sheet;
  const { score, coverage } = company;

  return (
    <section className="card">
      <div className="card-head">
        <h2>{id.name}</h2>
        {company.fictional && <span className="pill pill-fictiv">FICTIV</span>}
      </div>

      <div className="score-row">
        <BandBadge band={score.band} />
        <span className="score-value">{score.score}</span>
        <span className="muted">/ 100</span>
        <span className="coverage">
          {coverage.sources_available}/{coverage.sources_total} sources ({coverage.coverage_pct}%)
        </span>
      </div>

      {score.auto_stop_reasons.length > 0 && (
        <ul className="stop-reasons">
          {score.auto_stop_reasons.map((reason) => (
            <li key={reason}>
              <strong>STOP:</strong> {reason}
            </li>
          ))}
        </ul>
      )}

      <dl className="facts">
        <div>
          <dt>CUI</dt>
          <dd>{company.cui}</dd>
        </div>
        <div>
          <dt>Reg. number</dt>
          <dd>{id.reg_number}</dd>
        </div>
        <div>
          <dt>Legal form</dt>
          <dd>{id.legal_form}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>{id.status}</dd>
        </div>
        <div>
          <dt>Founded</dt>
          <dd>{id.founded_at}</dd>
        </div>
        <div>
          <dt>CAEN</dt>
          <dd>
            {id.caen.code} ({id.caen.version})
          </dd>
        </div>
      </dl>

      <dl className="facts">
        <div>
          <dt>Registered office</dt>
          <dd>
            {id.registered_office.text}
            <span className="muted small">
              {' '}
              · {id.registered_office.companies_at_same_address} companies at this address
            </span>
          </dd>
        </div>
      </dl>

      <div className="people">
        <div>
          <h4 className="subhead">Administrators</h4>
          <ul>
            {id.administrators.map((a) => (
              <li key={a.name + a.since}>
                {a.name} <span className="muted small">· {a.since} → {a.until ?? 'present'}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="subhead">Shareholders</h4>
          <ul>
            {id.shareholders.map((s) => (
              <li key={s.cui ?? s.name}>
                {s.name} <span className="muted small">· {s.share_pct}%</span>{' '}
                {s.source_type === 'mock' && <span className="pill pill-mock">MOCK</span>}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
