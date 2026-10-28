// Mock analyst accounts table (FICTIV). Stands in for the bank's user database until the API
// has auth. `id` is what a review stores; the API's DecisionRequest.analyst is a string too.
// an-001..an-005 are invented people; an-006 was added by name at the team's request.
// E-mails use the reserved .example domain.

export const ANALYSTS = [
  {
    id: 'an-001',
    username: 'analist.emarinescu',
    name: 'Elena Marinescu',
    role: 'Senior credit analyst',
    email: 'elena.marinescu@bank.example',
  },
  {
    id: 'an-002',
    username: 'analist.mconstantin',
    name: 'Mihai Constantin',
    role: 'Credit analyst',
    email: 'mihai.constantin@bank.example',
  },
  {
    id: 'an-003',
    username: 'analist.istanciu',
    name: 'Ioana Stanciu',
    role: 'KYC analyst',
    email: 'ioana.stanciu@bank.example',
  },
  {
    id: 'an-004',
    username: 'analist.rpetrescu',
    name: 'Radu Petrescu',
    role: 'Risk analyst',
    email: 'radu.petrescu@bank.example',
  },
  {
    id: 'an-005',
    username: 'analist.blungu',
    name: 'Bianca Lungu',
    role: 'Junior credit analyst',
    email: 'bianca.lungu@bank.example',
  },
  {
    id: 'an-006',
    username: 'analist.bgeica',
    name: 'Bianca Geica',
    role: 'Senior analyst',
    email: 'bianca.geica@bank.example',
  },
];

// People responsible for client contracts (invented). Contact only: no login, so they are not
// in the "Signed in as" list.
export const RELATIONSHIP_MANAGERS = [
  {
    id: 'rm-001',
    name: 'Andreea Voicu',
    role: 'Relationship manager',
    email: 'andreea.voicu@bank.example',
  },
  {
    id: 'rm-002',
    name: 'Cristian Dobre',
    role: 'Relationship manager',
    email: 'cristian.dobre@bank.example',
  },
  {
    id: 'rm-003',
    name: 'Larisa Moldovan',
    role: 'Relationship manager',
    email: 'larisa.moldovan@bank.example',
  },
];

const BY_ID = Object.fromEntries(
  [...ANALYSTS, ...RELATIONSHIP_MANAGERS].map((p) => [p.id, p]),
);

/** The person (analyst or relationship manager) for an id, or null when it is not in the table. */
export function getAnalyst(id) {
  return BY_ID[id] ?? null;
}
