// The ONLY place the frontend gets data from. Shapes = the API's Pydantic models
// (verifirm/schema/api.py, exported as JSON Schema in docs/schema/).
//
// Three modes, picked in this order:
//  - "api": VITE_API_URL set (e.g. http://localhost:8000). Calls the real API.
//  - "snapshot": no VITE_API_URL, but snapshot/data.json exists (made by `npm run snapshot`).
//    The API's answers saved earlier, read offline. Git-ignored.
//  - "mock": neither. The team's fixture files (read-only).
// Our invented UI companies (FICTIV) are added in every mode, always read locally.

import { companiesResponse as uiMock, companyDetails, signalsByCui } from './mock/build.js';
import { fixtureCompanies } from './mock/realFixtures.js';

const API_URL = import.meta.env.VITE_API_URL;

// Optional file: the glob is simply empty when no snapshot has been taken.
const SNAPSHOT = Object.values(
  import.meta.glob('../snapshot/data.json', { eager: true, import: 'default' }),
)[0];

export const DATA_MODE = API_URL ? 'api' : SNAPSHOT ? 'snapshot' : 'mock';

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
