// The ONLY place the frontend gets data from. Shapes = the API's Pydantic models
// (verifirm/schema/api.py, exported as JSON Schema in docs/schema/).
//
// Three modes:
//  - "snapshot": snapshot/data.json, the API's answers saved by `npm run snapshot` and read
//    offline (git-ignored). The default whenever that file exists.
//  - "api": calls the real API at VITE_API_URL. Used when there is no snapshot, or when
//    VITE_DATA_SOURCE=live asks for the live server explicitly.
//  - "mock": neither. The team's fixture files (read-only).
// Our invented UI companies (FICTIV) are added in every mode, always read locally.

import { companiesResponse as uiMock, companyDetails, signalsByCui } from './mock/build.js';
import { fixtureCompanies } from './mock/realFixtures.js';
import { exampleOpinions } from './mock/analystOpinions.js';

// Optional file: the glob is simply empty when no snapshot has been taken.
const SNAPSHOT = Object.values(
  import.meta.glob('../snapshot/data.json', { eager: true, import: 'default' }),
)[0];

const WANT_LIVE = import.meta.env.VITE_DATA_SOURCE === 'live';

export const DATA_MODE =
  SNAPSHOT && !WANT_LIVE ? 'snapshot' : import.meta.env.VITE_API_URL ? 'api' : 'mock';

// Set only in "api" mode, so nothing else can reach the server by accident.
const API_URL = DATA_MODE === 'api' ? import.meta.env.VITE_API_URL : undefined;

/** When the snapshot in use was taken (ISO string), or null. */
export const SNAPSHOT_TAKEN_AT = DATA_MODE === 'snapshot' ? SNAPSHOT.taken_at : null;

export class NotFoundError extends Error {}

async function http(path) {
  const res = await fetch(`${API_URL}${path}`);
  if (res.status === 404) throw new NotFoundError(`Not found: ${path}`);
  if (!res.ok) throw new Error(`API error ${res.status} on ${path}`);
  return res.json();
}

/**
 * GET /companies -> { items, page, page_size, total }.
 * Each item also gets `origin` (frontend-only, not from the API): "backend" or "ui-mock".
 */
const uiMockItems = uiMock.items.map((i) => ({ ...i, origin: 'ui-mock' }));

// Our invented companies are answered locally in both modes.
const isUiMock = (cui) => cui in companyDetails;

export async function getCompanies() {
  let backendItems;
  if (API_URL) {
    const res = await http('/companies?page_size=200');
    backendItems = res.items;
  } else if (DATA_MODE === 'snapshot') {
    backendItems = SNAPSHOT.list.items;
  } else {
    backendItems = Object.values(fixtureCompanies)
      .filter((f) => f.list_item)
      .map((f) => f.list_item);
  }
  const items = [...backendItems.map((i) => ({ ...i, origin: 'backend' })), ...uiMockItems];
  return { items, page: 1, page_size: items.length, total: items.length };
}

/** GET /companies/{cui} -> { identity_sheet, score, band, components, coverage, sources, last_checked } */
export async function getCompany(cui) {
  if (isUiMock(cui)) return companyDetails[cui];
  if (API_URL) return http(`/companies/${cui}`);

  const company =
    DATA_MODE === 'snapshot' ? SNAPSHOT.companies[cui]?.company : fixtureCompanies[cui]?.company;
  if (!company) throw new NotFoundError(`Company ${cui} not found (404)`);
  return company;
}

/** GET /companies/{cui}/signals -> Signal[], or null when there is no data yet (404). */
export async function getSignals(cui) {
  if (isUiMock(cui)) return signalsByCui[cui] ?? null;
  if (API_URL) {
    try {
      return await http(`/companies/${cui}/signals`);
    } catch (e) {
      if (e instanceof NotFoundError) return null;
      throw e;
    }
  }
  if (DATA_MODE === 'snapshot') return SNAPSHOT.companies[cui]?.signals ?? null;
  return fixtureCompanies[cui]?.signals ?? null;
}

/**
 * GET /companies/{cui}/history -> { cui, date_from, date_to, scores[], events[], decisions[] },
 * all oldest first. null when there is none (404) or in offline mock mode (no history there).
 */
export async function getHistory(cui) {
  if (isUiMock(cui)) return null;
  if (DATA_MODE === 'snapshot') return SNAPSHOT.companies[cui]?.history ?? null;
  if (!API_URL) return null;
  try {
    return await http(`/companies/${cui}/history`);
  } catch (e) {
    if (e instanceof NotFoundError) return null;
    throw e;
  }
}

/**
 * GET /companies/{cui}/analyst-opinion -> the AI analyst's educated opinion (shown next to the
 * official score, never instead of it), or null when no run produced one yet (404).
 * Mock mode: an example opinion for some demo companies (mock/analystOpinions.js).
 */
export async function getAnalystOpinion(cui) {
  if (isUiMock(cui)) return null;
  if (DATA_MODE === 'snapshot') return SNAPSHOT.companies[cui]?.analyst_opinion ?? null;
  if (!API_URL) return exampleOpinions[cui] ?? null;
  try {
    return await http(`/companies/${cui}/analyst-opinion`);
  } catch (e) {
    if (e instanceof NotFoundError) return null;
    throw e;
  }
}
