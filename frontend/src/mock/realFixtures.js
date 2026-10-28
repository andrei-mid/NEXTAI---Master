// READ-ONLY view of the team's API fixtures (fixtures/companies/<cui>_<slug>/api/*.json).
// These are exactly the files the API serves in FIXTURE_MODE, so showing them here means the
// screens are tested against real backend data without running the API.
// The files belong to the fixtures/backend owners: never edit them from the frontend.

const files = import.meta.glob('../../../fixtures/companies/*/api/*.json', {
  eager: true,
  import: 'default',
});

/** cui -> { list_item, company, signals, memo, graph, run_events } (only the files that exist) */
export const fixtureCompanies = {};

for (const [path, json] of Object.entries(files)) {
  const match = path.match(/companies\/(\d+)_[^/]+\/api\/([a-z_]+)\.json$/);
  if (!match) continue;
  const [, cui, name] = match;
  fixtureCompanies[cui] ??= {};
  fixtureCompanies[cui][name] = json;
}
