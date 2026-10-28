import BandBadge from './BandBadge.jsx';
import OriginBadges from './OriginBadges.jsx';
import { coverageLabel, formatUtc, statusLabel } from '../format.js';

function PersonList({ people, showShare }) {
  if (people.length === 0) return <p className="muted small">None in the data.</p>;
  return (
    <ul>
      {people.map((p) => (
        <li key={p.name + (p.valid_from ?? '')}>
          {p.name}
          {showShare && p.share_pct != null && <span className="muted small"> · {p.share_pct}%</span>}
          <span className="muted small">
            {' '}
            · {p.valid_from ?? '?'} → {p.valid_to ?? 'present'}
          </span>{' '}
          {p.source?.type === 'mock' && <span className="pill pill-mock">MOCK</span>}
        </li>
      ))}
    </ul>
  );
}

/** Header of the company page, from GET /companies/{cui}. Shows the API's values as they are. */
export default function IdentityCard({ company, signals, origin }) {
  const id = company.identity_sheet;
  const stopSignals = company.band === 'stop' ? (signals ?? []).filter((s) => s.auto_stop_candidate) : [];
  const vat = id.vat_registered == null ? '—' : id.vat_registered ? 'Yes' : 'No';

  return (
    <section className="card">
      <div className="card-head">
        <h2>{id.current_name}</h2>
        <OriginBadges origin={origin} fictional={id.fictional} />
      </div>

      <div className="score-row">
        <BandBadge band={company.band} />
        <span className="score-value">{company.score ?? '—'}</span>
        <span className="muted">/ 100</span>
        <span className="coverage">{coverageLabel(company.coverage)}</span>
        {company.coverage?.missing?.length > 0 && (
          <span className="muted small">missing: {company.coverage.missing.join(', ')}</span>
        )}
      </div>
      <p className="muted small">Last checked: {formatUtc(company.last_checked)}</p>

      {company.band === 'stop' && (
        <ul className="stop-reasons">
          {stopSignals.length > 0 ? (
            stopSignals.map((s) => (
              <li key={s.signal_id}>
                <strong>STOP:</strong> {s.claim}
              </li>
            ))
          ) : (
            <li>
              <strong>STOP.</strong> The reasons are not included in the API response yet.
            </li>
          )}
        </ul>
      )}

      <dl className="facts">
        <div>
          <dt>CUI</dt>
          <dd>{id.cui}</dd>
        </div>
        <div>
          <dt>Trade register no.</dt>
          <dd>{id.trade_register_no ?? '—'}</dd>
        </div>
        <div>
          <dt>Legal form</dt>
          <dd>{id.legal_form ?? '—'}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>{statusLabel(id.status)}</dd>
        </div>
        <div>
          <dt>Registered</dt>
          <dd>{id.registration_date ?? '—'}</dd>
        </div>
        <div>
          <dt>CAEN</dt>
          <dd>
            {id.caen_code ?? '—'}
            {id.caen_revision && <span className="muted small"> ({id.caen_revision})</span>}
          </dd>
        </div>
        <div>
          <dt>VAT registered</dt>
          <dd>{vat}</dd>
        </div>
      </dl>

      <dl className="facts">
        <div>
          <dt>Registered office</dt>
          <dd>{id.registered_office?.raw ?? '—'}</dd>
        </div>
        {id.names.length > 1 && (
          <div>
            <dt>Former names</dt>
            <dd>
              {id.names
                .filter((n) => n.valid_to)
                .map((n) => n.name)
                .join(', ')}
            </dd>
          </div>
        )}
      </dl>

      <div className="people">
        <div>
          <h4 className="subhead">Administrators</h4>
          <PersonList people={id.administrators} />
        </div>
        <div>
          <h4 className="subhead">Shareholders</h4>
          <PersonList people={id.shareholders} showShare />
        </div>
      </div>
    </section>
  );
}
