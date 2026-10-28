import BandBadge from './BandBadge.jsx';

/** Left sidebar: one card per company (GET /companies item), already sorted by the caller. */
export default function AlertsSidebar({ items, selectedCui, onSelect }) {
  return (
    <aside className="sidebar" aria-label="Company alerts">
      <h2 className="sidebar-title">
        Alerts <span className="sidebar-count">{items.length}</span>
      </h2>
      <ul className="alert-list">
        {items.map((item) => {
          const severity = item.top_signal?.severity ?? 'info';
          return (
            <li key={item.cui}>
              <button
                type="button"
                className={`alert-item sev-border-${severity}${item.cui === selectedCui ? ' is-selected' : ''}`}
                aria-current={item.cui === selectedCui ? 'true' : undefined}
                onClick={() => onSelect(item.cui)}
              >
                <span className="alert-item-top">
                  <span className={`pill sev-${severity}`}>{severity}</span>
                  <BandBadge band={item.band} />
                  {item.fictional && <span className="pill pill-fictiv">FICTIV</span>}
                </span>
                <span className="alert-item-name">{item.name}</span>
                {item.top_signal && <span className="alert-item-claim">{item.top_signal.claim}</span>}
                <span className="alert-item-meta">
                  CUI {item.cui} · {item.coverage.sources_available}/{item.coverage.sources_total} sources
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
