// FRONTEND PROPOSAL, NOT IN THE API CONTRACT.
// Mock data for screens the contract does not cover yet:
//  - bank relationship (credit, loans, contracts): would come from the bank's own systems
//  - flag history: would need a read endpoint for past decisions, e.g. GET /companies/{cui}/decisions
// Everything here is invented (FICTIV). Not real bank data.

import { seeded } from './seeded.js';

const MOCK_TODAY = '2026-10-28';

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

/** Past analyst reviews for one company (mock). More severe companies have a longer history. */
export function getFlagHistory(cui, severity) {
  const r = seeded(Number(cui) + 7);
  const count = FLAG_COUNT[severity] ?? 2;
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
