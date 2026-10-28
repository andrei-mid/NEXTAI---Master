// Builds mock API responses from BASE_COMPANIES, in the exact shapes of
// "Contract de date API → Frontend": GET /companies, GET /companies/{cui},
// GET /companies/{cui}/signals. Everything is invented (FICTIV / MOCK).

import { BASE_COMPANIES } from './companies.js';
import { seeded } from './seeded.js';

const RETRIEVED_AT = '2026-10-28T08:00:00Z';

const COMPONENTS = ['identity', 'financials', 'tax', 'litigation', 'network', 'sanctions', 'media', 'presence'];
const WEIGHTS = { identity: 15, financials: 20, tax: 15, litigation: 15, network: 15, sanctions: 10, media: 5, presence: 5 };
const SOURCE_NAMES = {
  identity: ['ONRC open data', 'ANAF VAT registry v9'],
  financials: ['ANAF financial statements'],
  tax: ['ANAF VAT registry v9', 'Tax arrears list (MOCK)'],
  litigation: ['Portal Just', 'ICCJ', 'BPI (MOCK)'],
  network: ['ONRC open data', 'Shareholders (MOCK)'],
  sanctions: ['EU FSF', 'UN', 'OFAC'],
  media: ['Web search'],
  presence: ['Web', 'SEAP', 'Kohesio'],
};

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

function makeSignal(cui, index, t) {
  const official = t.source.type === 'official';
  return {
    signal_id: `sig_${cui}_${t.component.slice(0, 3)}_${String(index + 1).padStart(3, '0')}`,
    cui,
    agent: t.component,
    component: t.component,
    rule_id: t.rule_id,
    claim: t.claim,
    source: {
      name: t.source.name,
      type: t.source.type,
      url: t.source.url ? t.source.url.replace('{cui}', cui) : null,
      retrieved_at: t.source.url ? RETRIEVED_AT : null,
      raw_ref: null,
      content_hash: null,
    },
    evidence_date: t.evidence_date ?? null,
    confidence: official ? 0.95 : 0.7,
    severity: t.severity,
    validated: t.validated ?? true,
    auto_stop_candidate: t.severity === 'critical' && (t.validated ?? true),
    entity_match: { method: 'cui', score: 1, ambiguous: false },
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

function buildDetail(base, signals) {
  const r = seeded(Number(base.cui) + 29);
  const pick = (list) => list[Math.floor(r() * list.length)];

  const components = COMPONENTS.map((component) => {
    const available = !base.unavailable.includes(component);
    const n = signals.filter((s) => s.component === component).length;
    return {
      component,
      score: !available ? null : n === 0 ? 100 : Math.round(15 + r() * 70),
      weight: WEIGHTS[component],
      available,
      n_signals: n,
    };
  });

  const sources = COMPONENTS.map((component) => {
    const available = !base.unavailable.includes(component);
    return {
      agent: component,
      component,
      status: available ? 'ok' : 'unavailable',
      sources_checked: available ? SOURCE_NAMES[component] : [],
      sources_failed: available ? [] : SOURCE_NAMES[component],
      duration_ms: Math.round(800 + r() * 6000),
      notes: available ? null : 'The source did not respond (MOCK).',
    };
  });

  const adminSince = `${Number(base.founded_at.slice(0, 4)) + 3}-01-15`;
  const shareholder = BASE_COMPANIES.find((c) => c.cui !== base.cui && c.band === 'green');

  return {
    cui: base.cui,
    fictional: true,
    identity_sheet: {
      name: base.name,
      name_history: [],
      reg_number: `J99/${base.cui.slice(-4)}/${base.founded_at.slice(0, 4)}`,
      legal_form: 'SRL',
      status: base.status,
      founded_at: base.founded_at,
      caen: { code: base.caen, version: 'rev2' },
      registered_office: {
        text: `Str. Exemplului nr. ${Number(base.cui.slice(-2))}, Sector 9, București`,
        companies_at_same_address: Math.round(1 + r() * 60),
      },
      administrators: [
        { name: pick(PEOPLE), role: 'administrator', since: adminSince, until: null },
        { name: pick(PEOPLE), role: 'administrator', since: base.founded_at, until: adminSince },
      ],
      shareholders: [{ name: shareholder.name, cui: shareholder.cui, share_pct: 100, source_type: 'mock' }],
    },
    score: {
      run_id: `run_${base.cui}`,
      score: base.score,
      band: base.band,
      auto_stop_reasons: base.auto_stop_reasons,
      weights_version: 'proposal-v1',
    },
    coverage: {
      coverage_pct: base.coverage_pct,
      sources_available: COMPONENTS.length - base.unavailable.length,
      sources_total: COMPONENTS.length,
    },
    components,
    sources,
  };
}

export const signalsByCui = {};
export const companyDetails = {};
const items = [];

for (const base of BASE_COMPANIES) {
  const signals = buildSignals(base);
  const detail = buildDetail(base, signals);
  const top = signals[0];
  signalsByCui[base.cui] = signals;
  companyDetails[base.cui] = detail;
  items.push({
    cui: base.cui,
    name: base.name,
    band: base.band,
    score: base.score,
    coverage: detail.coverage,
    last_checked: base.last_checked,
    top_signal: { signal_id: top.signal_id, component: top.component, severity: top.severity, claim: top.claim },
    fictional: true,
  });
}

export const companiesResponse = { items, page: 1, page_size: 50, total: items.length };
