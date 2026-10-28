// Builds mock API responses from BASE_COMPANIES, in the exact shapes of the API's Pydantic
// models (verifirm/schema/api.py, signals.py, identity.py, scoring.py):
// GET /companies, GET /companies/{cui}, GET /companies/{cui}/signals.
// Everything is invented (FICTIV / MOCK).

import { BASE_COMPANIES } from './companies.js';
import { seeded } from './seeded.js';

const RETRIEVED_AT = '2026-10-28T08:00:00Z';

const COMPONENTS = ['identity', 'financials', 'tax', 'litigation', 'network', 'sanctions', 'media', 'presence'];
const WEIGHTS = { identity: 15, financials: 20, tax: 15, litigation: 15, network: 15, sanctions: 10, media: 5, presence: 5 };

const EXTRA_SIGNALS = [
  {
    component: 'tax',
    rule_id: 'TAX-DECLARED-GAP-01',
    claim: 'Declared VAT (D300) is 18% below e-Factura invoices for Q2 2026.',
    severity: 'high',
    evidence_date: '2026-06-30',
    source: { name: 'RO e-Factura (MOCK)', type: 'mock', url: 'https://efactura.example/{cui}/2026-q2' },
  },
  {
    component: 'litigation',
    rule_id: 'LIT-CASE-01',
    claim: 'Defendant in a 1,200,000 RON claim (case 9402/99/2026), first instance.',
    severity: 'medium',
    evidence_date: '2026-03-11',
    source: { name: 'portal.just.ro', type: 'official', url: 'https://portal-just.example/dosar/9402-99-2026' },
  },
  {
    component: 'identity',
    rule_id: 'ID-ADMIN-CHANGE-01',
    claim: 'Administrator changed on 2025-11-02.',
    severity: 'medium',
    evidence_date: '2025-11-02',
    source: { name: 'ONRC open data', type: 'official', url: 'https://onrc.example/firma/{cui}/istoric' },
  },
  {
    component: 'financials',
    rule_id: 'FIN-DEBT-RISE-01',
    claim: 'Total debts doubled between 2024 and 2025.',
    severity: 'medium',
    evidence_date: '2025-12-31',
    source: { name: 'ANAF financial statements', type: 'official', url: 'https://anaf.example/bilant/2025/{cui}' },
  },
  {
    component: 'network',
    rule_id: 'NET-SHARED-OFFICE-01',
    claim: 'Registered office shared with 37 other companies.',
    severity: 'low',
    evidence_date: '2026-10-20',
    source: { name: 'ONRC open data', type: 'official', url: 'https://onrc.example/sediu/{cui}' },
  },
  {
    component: 'presence',
    rule_id: 'PRE-NO-FOOTPRINT-01',
    claim: 'No website, job ads or public procurement found.',
    severity: 'low',
    evidence_date: '2026-10-28',
    source: { name: 'Public footprint (web)', type: 'web', url: 'https://cautare.example/?q={cui}' },
  },
];

const EXTRA_COUNT = { critical: 3, high: 3, medium: 2, low: 1, info: 0 };

// One company deliberately gets a claim WITHOUT a link, to show how the UI flags it.
const UNSOURCED_DEMO_CUI = '99001061';

const PEOPLE = ['Dorina Inventescu', 'Marius Imaginaru', 'Elena Fictiveanu', 'Radu Exemplaru', 'Sorina Nascocita'];

/** SourceRef */
function sourceRef(s, cui) {
  return {
    name: s.name,
    type: s.type,
    url: s.url ? s.url.replace('{cui}', cui) : null,
    retrieved_at: RETRIEVED_AT,
    raw_ref: null,
    content_hash: null,
  };
}

/** Signal */
function makeSignal(cui, index, t) {
  const validated = t.validated ?? true;
  return {
    signal_id: `${t.rule_id}:mock${cui}${index}`,
    cui,
    agent: t.component,
    component: t.component,
    rule_id: t.rule_id,
    claim: t.claim,
    source: sourceRef(t.source, cui),
    evidence_date: t.evidence_date ?? null,
    confidence: t.source.type === 'official' ? 0.95 : 0.7,
    severity: t.severity,
    validated,
    auto_stop_candidate: t.severity === 'critical' && validated,
    entity_match: { method: 'cui_exact', score: 1, ambiguous: false },
    data: {},
  };
}

function buildSignals(base) {
  const r = seeded(Number(base.cui) + 13);
  const pool = EXTRA_SIGNALS.filter(
    (t) => t.rule_id !== base.top.rule_id && !base.unavailable.includes(t.component),
  );
  const offset = Math.floor(r() * pool.length);
  const count = Math.min(EXTRA_COUNT[base.top.severity] ?? 0, pool.length);
  const templates = [base.top, ...Array.from({ length: count }, (_, i) => pool[(offset + i) % pool.length])];

  if (base.cui === UNSOURCED_DEMO_CUI) {
    templates.push({
      component: 'network',
      rule_id: 'NET-LINKED-ADMIN-01',
      claim: 'Possible link to another company through a shared administrator.',
      severity: 'medium',
      evidence_date: null,
      source: { name: 'Network agent', type: 'official', url: null },
    });
  }

  return templates.map((t, i) => makeSignal(base.cui, i, t));
}

/** Coverage */
function buildCoverage(base) {
  const available = COMPONENTS.filter((c) => !base.unavailable.includes(c));
  return {
    weight_pct: available.reduce((sum, c) => sum + WEIGHTS[c], 0),
    available: available.length,
    total: COMPONENTS.length,
    missing: [...base.unavailable],
  };
}

/** CompanyDetail */
function buildDetail(base, signals) {
  const r = seeded(Number(base.cui) + 29);
  const pick = (list) => list[Math.floor(r() * list.length)];
  const coverage = buildCoverage(base);

  const components = COMPONENTS.map((component) => {
    const available = !base.unavailable.includes(component);
    const ids = signals.filter((s) => s.component === component).map((s) => s.signal_id);
    return {
      component,
      status: available ? 'ok' : 'unavailable',
      available,
      score: !available ? null : ids.length === 0 ? 100 : Math.round(15 + r() * 70),
      weight: WEIGHTS[component],
      effective_weight: available ? Math.round((WEIGHTS[component] / coverage.weight_pct) * 1000) / 1000 : 0,
      signal_ids: ids,
    };
  });

  const onrc = sourceRef({ name: 'ONRC open data', type: 'official', url: 'https://onrc.example/firma/{cui}' }, base.cui);
  const anaf = sourceRef({ name: 'ANAF VAT registry v9', type: 'official', url: 'https://anaf.example/registru-tva/{cui}' }, base.cui);
  const shareholdersMock = sourceRef({ name: 'Shareholders (MOCK)', type: 'mock', url: null }, base.cui);

  const adminSince = `${Number(base.founded_at.slice(0, 4)) + 3}-01-15`;
  const shareholder = BASE_COMPANIES.find((c) => c.cui !== base.cui && c.band === 'green');
  const office = {
    raw: `Str. Exemplului nr. ${Number(base.cui.slice(-2))}, Sector 9, București`,
    county: 'București',
    locality: null,
    street: null,
    number: null,
    postal_code: null,
    valid_from: base.founded_at,
    valid_to: null,
  };
  const person = (name, from, to) => ({
    name,
    role: 'administrator',
    is_company: false,
    cui: null,
    share_pct: null,
    valid_from: from,
    valid_to: to,
    source: onrc,
  });

  const sources = [anaf, onrc, ...signals.map((s) => s.source)].filter(
    (s, i, all) => all.findIndex((x) => x.name === s.name) === i,
  );

  return {
    identity_sheet: {
      cui: base.cui,
      fictional: true,
      trade_register_no: `J99/${base.cui.slice(-4)}/${base.founded_at.slice(0, 4)}`,
      current_name: base.name,
      names: [{ name: base.name, valid_from: base.founded_at, valid_to: null }],
      legal_form: 'SRL',
      status: base.status,
      registration_date: base.founded_at,
      registered_office: office,
      office_history: [office],
      caen_code: base.caen,
      caen_revision: 'rev2',
      authorized_caen_codes: [base.caen],
      administrators: [person(pick(PEOPLE), adminSince, null), person(pick(PEOPLE), base.founded_at, adminSince)],
      shareholders: [
        {
          name: shareholder.name,
          role: 'shareholder',
          is_company: true,
          cui: shareholder.cui,
          share_pct: 100,
          valid_from: base.founded_at,
          valid_to: null,
          source: shareholdersMock,
        },
      ],
      vat_registered: base.top.rule_id !== 'TAX-VAT-CANCELLED-01',
      anaf_inactive: base.status === 'inactive_anaf',
      sources: [anaf, onrc],
    },
    score: base.score,
    band: base.band,
    components,
    coverage,
    sources,
    last_checked: base.last_checked,
  };
}

export const signalsByCui = {};
export const companyDetails = {};
const items = [];

for (const base of BASE_COMPANIES) {
  const signals = buildSignals(base);
  const detail = buildDetail(base, signals);
  signalsByCui[base.cui] = signals;
  companyDetails[base.cui] = detail;
  items.push({
    cui: base.cui,
    name: base.name,
    band: base.band,
    score: base.score,
    coverage: detail.coverage,
    last_checked: base.last_checked,
    top_signal: { rule_id: base.top.rule_id, claim: base.top.claim, severity: base.top.severity },
    fictional: true,
  });
}

/** CompanyList */
export const companiesResponse = { items, page: 1, page_size: 50, total: items.length };
