// Order for display only: severity comes from the API as-is, we never re-score it.
const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low', 'info'];

export function sortByCriticality(items) {
  return [...items].sort(
    (a, b) =>
      SEVERITY_ORDER.indexOf(a.alert.severity) - SEVERITY_ORDER.indexOf(b.alert.severity) ||
      b.last_checked.localeCompare(a.last_checked),
  );
}

export default function AlertsSidebar({ items, selectedCui, onSelect }) {
  return (
    <aside className="sidebar" aria-label="Company alerts">
      <h2 className="sidebar-title">
        Alerts <span className="sidebar-count">{items.length}</span>
      </h2>
      <ul className="alert-list">
        {items.map((item) => (
          <li key={item.cui}>
            <button
              type="button"
              className={`alert-item sev-border-${item.alert.severity}${
                item.cui === selectedCui ? ' is-selected' : ''
              }`}
              aria-current={item.cui === selectedCui ? 'true' : undefined}
              onClick={() => onSelect(item.cui)}
            >
              <span className="alert-item-top">
                <span className={`pill sev-${item.alert.severity}`}>{item.alert.severity}</span>
                {item.fictional && <span className="pill pill-fictiv">FICTIV</span>}
                {item.alert.source.type === 'mock' && <span className="pill pill-mock">MOCK</span>}
                {!item.alert.validated && <span className="pill pill-unvalidated">unvalidated</span>}
              </span>
              <span className="alert-item-name">{item.name}</span>
              <span className="alert-item-claim">{item.alert.claim}</span>
              <span className="alert-item-meta">
                CUI {item.cui} · {item.coverage.available}/{item.coverage.total} sources
              </span>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
