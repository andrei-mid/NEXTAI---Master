import { daysUntil, formatRon } from '../format.js';

const SOON_DAYS = 90;

function EndBadge({ contract }) {
  const days = daysUntil(contract.end);
  const verb = contract.end_type === 'renewal' ? 'Renewal' : 'Ends';
  if (days < 0) return <span className="pill pill-expired">{verb}: overdue</span>;
  if (days <= SOON_DAYS) return <span className="pill pill-soon">{verb} in {days} days</span>;
  return <span className="pill pill-outcome">{verb} in {days} days</span>;
}

export default function BankRelationship({ bank }) {
  const next = bank.contracts[0];

  return (
    <section className="card">
      <div className="card-head">
        <h3>Relationship with the bank</h3>
        <span className="pill pill-mock">MOCK</span>
        <span className="pill pill-proposal">not in API contract</span>
      </div>
      <p className="muted small">
        Fictional numbers for the mockup. Not real bank data. The real version would come from the
        bank's own systems.
      </p>

      <dl className="facts">
        <div>
          <dt>Client since</dt>
          <dd>{bank.client_since}</dd>
        </div>
        <div>
          <dt>Segment</dt>
          <dd>{bank.segment}</dd>
        </div>
        <div>
          <dt>Relationship team</dt>
          <dd>{bank.relationship_team}</dd>
        </div>
      </dl>

      <div className="tiles">
        <div className="tile">
          <span className="tile-label">Total credit limits</span>
          <span className="tile-value">{formatRon(bank.total_limit)}</span>
        </div>
        <div className="tile">
          <span className="tile-label">Drawn / outstanding</span>
          <span className="tile-value">{formatRon(bank.total_used)}</span>
        </div>
        <div className="tile">
          <span className="tile-label">Current account balance</span>
          <span className="tile-value">{formatRon(bank.account_balance)}</span>
        </div>
        {next && (
          <div className="tile">
            <span className="tile-label">Next contract date</span>
            <span className="tile-value">{next.end}</span>
            <span className="muted small">{next.product}</span>
          </div>
        )}
      </div>

      <h4 className="subhead">Credit products and contracts</h4>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Product</th>
              <th>Contract</th>
              <th>Limit / amount</th>
              <th>Drawn / outstanding</th>
              <th>Start</th>
              <th>End</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {bank.contracts.map((c) => (
              <tr key={c.contract_no}>
                <td>{c.product}</td>
                <td className="nowrap muted">{c.contract_no}</td>
                <td className="nowrap">{formatRon(c.limit)}</td>
                <td className="nowrap">
                  {formatRon(c.used)}
                  <span className="usage-bar" aria-hidden="true">
                    <span style={{ width: `${Math.min(100, (c.used / c.limit) * 100)}%` }} />
                  </span>
                </td>
                <td className="nowrap">{c.start}</td>
                <td className="nowrap">{c.end}</td>
                <td>
                  <EndBadge contract={c} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
