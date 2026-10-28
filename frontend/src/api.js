// The ONLY place the frontend gets data from. Shapes = the API's Pydantic models
// (verifirm/schema/api.py, exported as JSON Schema in docs/schema/).
//
// Two modes:
//  - VITE_API_URL set (e.g. http://localhost:8000): calls the real API.
//  - not set: offline mock = the team's fixture files (read-only) + our invented UI companies.

import { companiesResponse as uiMock, companyDetails, signalsByCui } from './mock/build.js';
import { fixtureCompanies } from './mock/realFixtures.js';

const API_URL = import.meta.env.VITE_API_URL;

export const DATA_MODE = API_URL ? 'api' : 'mock';

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
export async function getCompanies() {
  if (API_URL) {
    const res = await http('/companies?page_size=200');
    return { ...res, items: res.items.map((i) => ({ ...i, origin: 'backend' })) };
  }

  const fixtureItems = Object.values(fixtureCompanies)
    .filter((f) => f.list_item)
    .map((f) => ({ ...f.list_item, origin: 'backend' }));
  const items = [...fixtureItems, ...uiMock.items.map((i) => ({ ...i, origin: 'ui-mock' }))];
  return { items, page: 1, page_size: items.length, total: items.length };
}

/** GET /companies/{cui} -> { identity_sheet, score, band, components, coverage, sources, last_checked } */
export async function getCompany(cui) {
  if (API_URL) return http(`/companies/${cui}`);

  const company = fixtureCompanies[cui]?.company ?? companyDetails[cui];
  if (!company) throw new NotFoundError(`Company ${cui} not found (404)`);
  return company;
}

/** GET /companies/{cui}/signals -> Signal[], or null when there is no data yet (404). */
export async function getSignals(cui) {
  if (API_URL) {
    try {
      return await http(`/companies/${cui}/signals`);
    } catch (e) {
      if (e instanceof NotFoundError) return null;
      throw e;
    }
  }
  if (fixtureCompanies[cui]) return fixtureCompanies[cui].signals ?? null;
  return signalsByCui[cui] ?? null;
}
