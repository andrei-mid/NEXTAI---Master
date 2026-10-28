import { useEffect, useState } from 'react';
import { getCompany, getSignals } from '../api.js';
import { getBankRelationship, getFlagHistory } from '../mock/frontendExtras.js';
import { sortSignals } from '../severity.js';
import IdentityCard from './IdentityCard.jsx';
import ComponentBars from './ComponentBars.jsx';
import ClaimsList from './ClaimsList.jsx';
import FlagHistory from './FlagHistory.jsx';
import BankRelationship from './BankRelationship.jsx';

/** Centre of the page for one company: loads GET /companies/{cui} and /signals. */
export default function CompanyDetail({ item, sessionReviews }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    setData(null);
    setError(null);
    Promise.all([getCompany(item.cui), getSignals(item.cui)])
      .then(([company, signals]) => active && setData({ company, signals }))
      .catch((e) => active && setError(e));
    return () => {
      active = false;
    };
  }, [item.cui]);

  if (error) {
    return <div className="card source-missing">Could not load this company: {error.message}</div>;
  }
  if (!data) return <p className="muted">Loading…</p>;

  const { company, signals } = data;
  // Invented history and bank figures are only ever shown next to fictional companies,
  // never next to a real company (e.g. Dedeman).
  const fictional = company.identity_sheet.fictional;
  const mockHistory = fictional ? getFlagHistory(item.cui, item.top_signal?.severity) : [];
  const history = [...mockHistory, ...sessionReviews];

  return (
    <div className="detail">
      <IdentityCard company={company} signals={signals} origin={item.origin} />
      <ComponentBars components={company.components} />
      <ClaimsList claims={signals && sortSignals(signals)} lastChecked={company.last_checked} />
      <FlagHistory entries={history} />
      {fictional ? (
        <BankRelationship bank={getBankRelationship(item.cui)} />
      ) : (
        <section className="card">
          <h3>Relationship with the bank</h3>
          <p className="muted">
            Not shown: this is a real company and the mockup only uses invented bank data for fictional
            companies.
          </p>
        </section>
      )}
    </div>
  );
}
