// MOCK data for the company detail mockup. Everything here is invented (FICTIV):
// bank products, amounts, contracts and past analyst flags. Not real bank data.
// Values are generated from the CUI, so each company always gets the same mock data.

const MOCK_TODAY = '2026-10-28';

/** Small seeded random generator: same CUI -> same numbers on every reload. */
function seeded(seed) {
  let s = seed % 2147483647 || 1;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

function shiftMonths(months) {
  const d = new Date(`${MOCK_TODAY}T00:00:00Z`);
  d.setUTCMonth(d.getUTCMonth() + months);
  return d.toISOString().slice(0, 10);
}

/** Bank products, credit and contracts for one company. */
export function getBankRelationship(cui) {
  const r = seeded(Number(cui));
  const tag = cui.slice(-4);
  const between = (min, max) => Math.round(min + r() * (max - min));
  const money = (min, max, step) => Math.round(between(min, max) / step) * step;

  const contracts = [];

  const lineLimit = money(500_000, 3_000_000, 50_000);
  contracts.push({
    product: 'Revolving credit line',
    contract_no: `FICTIV-CL-${tag}`,
    limit: lineLimit,
    used: money(lineLimit * 0.2, lineLimit * 0.95, 10_000),
    start: shiftMonths(-between(10, 30)),
    end: shiftMonths(between(1, 8)),
    end_type: 'renewal',
  });

  const loan = money(1_000_000, 8_000_000, 100_000);
  contracts.push({
    product: 'Investment loan',
    contract_no: `FICTIV-IL-${tag}`,
    limit: loan,
    used: money(loan * 0.3, loan * 0.9, 10_000),
    start: shiftMonths(-between(12, 48)),
    end: shiftMonths(between(18, 60)),
    end_type: 'ends',
  });

  if (r() > 0.4) {
    const amount = money(100_000, 800_000, 10_000);
    contracts.push({
      product: 'Letter of bank guarantee',
      contract_no: `FICTIV-BG-${tag}`,
      limit: amount,
      used: amount,
      start: shiftMonths(-between(3, 12)),
      end: shiftMonths(between(2, 14)),
      end_type: 'ends',
    });
  }

  if (r() > 0.5) {
    const limit = money(300_000, 1_500_000, 50_000);
    contracts.push({
      product: 'Factoring line',
      contract_no: `FICTIV-FA-${tag}`,
      limit,
      used: money(limit * 0.1, limit * 0.8, 10_000),
      start: shiftMonths(-between(6, 24)),
      end: shiftMonths(between(3, 12)),
      end_type: 'renewal',
    });
  }

  contracts.sort((a, b) => a.end.localeCompare(b.end));

  return {
    client_since: shiftMonths(-between(30, 120)),
    segment: 'Corporate (FICTIV)',
    relationship_team: `Corporate team ${['North', 'South', 'East', 'West'][between(0, 3)]} (FICTIV)`,
    account_balance: money(50_000, 2_000_000, 1_000),
    total_limit: contracts.reduce((sum, c) => sum + c.limit, 0),
    total_used: contracts.reduce((sum, c) => sum + c.used, 0),
    contracts,
  };
}

const CLAIM_TEMPLATES = [
  {
    rule_id: 'TAX-DECLARED-GAP-01',
    claim: 'Declared VAT (D300) is 18% below e-Factura invoices for Q2 2026.',
    severity: 'high',
    evidence_date: '2026-06-30',
    source: { name: 'RO e-Factura (MOCK)', type: 'mock', url: 'https://efactura.example/{cui}/2026-q2' },
  },
  {
    rule_id: 'LIT-CASE-01',
    claim: 'Defendant in a 1,200,000 RON claim (case 9402/99/2026), first instance.',
    severity: 'medium',
    evidence_date: '2026-03-11',
    source: { name: 'portal.just.ro', type: 'official', url: 'https://portal-just.example/dosar/9402-99-2026' },
  },
  {
    rule_id: 'ID-ADMIN-CHANGE-01',
    claim: 'Administrator changed on 2025-11-02.',
    severity: 'medium',
    evidence_date: '2025-11-02',
    source: { name: 'ONRC open data', type: 'official', url: 'https://onrc.example/firma/{cui}/istoric' },
  },
  {
    rule_id: 'FIN-REVENUE-DROP-01',
    claim: 'Turnover fell 41% between 2024 and 2025.',
    severity: 'medium',
    evidence_date: '2025-12-31',
    source: { name: 'ANAF financial statements', type: 'official', url: 'https://anaf.example/bilant/2025/{cui}' },
  },
  {
    rule_id: 'NET-SHARED-OFFICE-01',
    claim: 'Registered office shared with 37 other companies.',
    severity: 'low',
    evidence_date: '2026-10-20',
    source: { name: 'ONRC open data', type: 'official', url: 'https://onrc.example/sediu/{cui}' },
  },
];

const EXTRA_CLAIMS = { critical: 3, high: 3, medium: 2, low: 1, info: 0 };

// One company deliberately gets a claim WITHOUT a link, to show how the UI flags it.
const UNSOURCED_DEMO_CUI = '99001061';

/** All claims for one company: its top alert first, then the others. Each carries its source. */
export function getClaims(company) {
  const r = seeded(Number(company.cui) + 13);
  const offset = Math.floor(r() * CLAIM_TEMPLATES.length);
  const count = EXTRA_CLAIMS[company.alert.severity] ?? 0;

  const extra = Array.from({ length: count }, (_, i) => {
    const t = CLAIM_TEMPLATES[(offset + i) % CLAIM_TEMPLATES.length];
    return {
      ...t,
      validated: true,
      source: {
        ...t.source,
        url: t.source.url.replace('{cui}', company.cui),
        retrieved_at: '2026-10-28T08:00:00Z',
      },
    };
  });

  if (company.cui === UNSOURCED_DEMO_CUI) {
    extra.push({
      rule_id: 'SAN-NAME-SIMILAR-01',
      claim: 'Name is similar to an entry on a sanctions list.',
      severity: 'medium',
      validated: false,
      evidence_date: null,
      source: { name: 'Sanctions check', type: 'official', url: null, retrieved_at: null },
    });
  }

  return [company.alert, ...extra];
}

const FLAG_TEMPLATES = [
  { choice: 'registry_mismatch', comment: 'ONRC shows the company as active, ANAF lists it as inactive. Asked the client for clarification.' },
  { choice: 'escalate', comment: 'Sent to the risk committee after a second overdue tax notice.' },
  { choice: 'no_risk', comment: 'Registered office change confirmed with documents.' },
  { choice: 'unreliable_data', comment: 'Turnover in the submitted PDF does not match ANAF financial statements.' },
  { choice: 'false_positive', comment: 'The court case belonged to a different company with a similar name.' },
  { choice: 'escalate', comment: 'Administrator is linked to two struck-off companies.' },
  { choice: 'registry_mismatch', comment: 'Registered office differs between ONRC and ANAF records.' },
  { choice: 'no_risk', comment: 'Media mention reviewed, not related to this company.' },
];

const FLAG_COUNT = { critical: 7, high: 6, medium: 4, low: 3, info: 2 };

/** Past analyst reviews for one company (mock). Newest first. */
export function getFlagHistory(company) {
  const r = seeded(Number(company.cui) + 7);
  const count = FLAG_COUNT[company.alert.severity] ?? 2;
  const offset = Math.floor(r() * FLAG_TEMPLATES.length);

  let monthsBack = 0;
  return Array.from({ length: count }, (_, i) => {
    monthsBack += 1 + Math.floor(r() * 3);
    const template = FLAG_TEMPLATES[(offset + i) % FLAG_TEMPLATES.length];
    return {
      ...template,
      recorded_at: `${shiftMonths(-monthsBack)}T09:00:00Z`,
      analyst: `Analyst ${'ABCD'[Math.floor(r() * 4)]} (FICTIV)`,
    };
  });
}
