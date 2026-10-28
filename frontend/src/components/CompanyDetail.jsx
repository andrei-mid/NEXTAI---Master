import { getBankRelationship, getClaims, getFlagHistory } from '../mockCompanyDetails.js';
import ClaimsList from './ClaimsList.jsx';
import FlagHistory from './FlagHistory.jsx';
import BankRelationship from './BankRelationship.jsx';
import SourceLink from './SourceLink.jsx';

export default function CompanyDetail({ company, sessionReviews }) {
  const claims = getClaims(company);
  const bank = getBankRelationship(company.cui);
  const history = [...getFlagHistory(company), ...sessionReviews];

  return (
    <div className="detail">
      <section className="card">
        <div className="card-head">
          <h2>{company.name}</h2>
          {company.fictional && <span className="pill pill-fictiv">FICTIV</span>}
        </div>
        <p className="muted">
          CUI {company.cui} · {company.coverage.available}/{company.coverage.total} sources (
          {company.coverage.weight_pct}%)
        </p>
        <div className="current-alert">
          <span className={`pill sev-${company.alert.severity}`}>{company.alert.severity}</span>
          <span>{company.alert.claim}</span>
        </div>
        <SourceLink source={company.alert.source} evidenceDate={company.alert.evidence_date} />
      </section>

      <ClaimsList claims={claims} />
      <FlagHistory entries={history} />
      <BankRelationship bank={bank} />
    </div>
  );
}
