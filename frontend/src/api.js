// The ONLY place the frontend gets data from.
//
// Today: mock data in the shapes of "Contract de date API → Frontend".
// Later: replace each function body with a fetch to the real API, for example
//   const res = await fetch(`${import.meta.env.VITE_API_URL}/companies`);
// The screens don't change, as long as the API keeps the same shapes.

import { companiesResponse, companyDetails, signalsByCui } from './mock/build.js';

/** GET /companies -> { items, page, page_size, total } */
export async function getCompanies() {
  return companiesResponse;
}

/** GET /companies/{cui} -> { cui, fictional, identity_sheet, score, coverage, components, sources } */
export async function getCompany(cui) {
  const company = companyDetails[cui];
  if (!company) throw new Error(`Company ${cui} not found (404)`);
  return company;
}

/** GET /companies/{cui}/signals -> Signal[] */
export async function getSignals(cui) {
  return signalsByCui[cui] ?? [];
}
