import { useEffect, useState } from 'react';
import { DATA_MODE, getCompany, getHistory, getSignals } from '../api.js';
import { getBankRelationship, getFlagHistory } from '../mock/frontendExtras.js';
import { sortSignals } from '../severity.js';
import IdentityCard from './IdentityCard.jsx';
import ComponentBars from './ComponentBars.jsx';
import ClaimsList from './ClaimsList.jsx';
import FlagHistory from './FlagHistory.jsx';
import BankRelationship from './BankRelationship.jsx';
import CheckHistory from './CheckHistory.jsx';

/**
 * Centre of the page for one company: GET /companies/{cui} and /signals first, then /history
 * on its own, so a slow history never holds back the rest of the page.
 */
export default function CompanyDetail({ item, sessionReviews, analystId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  // undefined = still loading, null = none or failed
  const [checkHistory, setCheckHistory] = useState(undefined);

  useEffect(() => {
    let active = true;
    setData(null);
    setError(null);
    setCheckHistory(undefined);
    Promise.all([getCompany(item.cui), getSignals(item.cui)])
      .then(([company, signals]) => active && setData({ company, signals }))
      .catch((e) => active && setError(e));
    getHistory(item.cui)
      .catch(() => null)
      .then((h) => active && setCheckHistory(h));
    return () => {
      active = false;
    };
  }, [item.cui]);

  if (error) {
    return <div className="card source-missing">Could not load this company: {error.message}</div>;
  }
  if (!data) {
    return (
      <p className="muted">
        Loading {item.name}
        {DATA_MODE === 'api' ? ' from the server (can take a few seconds)…' : '…'}
      </p>
    );
  }

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
      <ClaimsList
        claims={signals && sortSignals(signals)}
        lastChecked={company.last_checked}
        coverage={company.coverage}
      />
      {DATA_MODE === 'api' && item.origin === 'backend' && <CheckHistory history={checkHistory} />}
      <FlagHistory
        entries={history}
        companyName={company.identity_sheet.current_name}
        analystId={analystId}
      />
      {fictional ? (
        <BankRelationship
          bank={getBankRelationship(item.cui)}
          companyName={company.identity_sheet.current_name}
          analystId={analystId}
        />
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
