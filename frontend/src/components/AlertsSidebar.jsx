import BandBadge from './BandBadge.jsx';
import OriginBadges from './OriginBadges.jsx';
import { coverageLabel } from '../format.js';

/**
 * Left sidebar: one compact card per company (GET /companies item), already sorted by the
 * caller. Severity is the coloured left border; CUI and coverage are on the company page.
 * collapsed: only a thin strip with the button to open it again.
 */
export default function AlertsSidebar({ items, selectedCui, onSelect, collapsed, onToggle }) {
  if (collapsed) {
    return (
      <aside className="sidebar is-collapsed" aria-label="Company alerts">
        <button
          type="button"
          className="sidebar-toggle"
          aria-expanded="false"
          aria-label="Show the alerts list"
          title="Show the alerts list"
          onClick={onToggle}
        >
          ›
        </button>
        <span className="sidebar-rail-label">Alerts · {items.length}</span>
      </aside>
    );
  }

  return (
    <aside className="sidebar" aria-label="Company alerts">
      <h2 className="sidebar-title">
        Alerts <span className="sidebar-count">{items.length}</span>
        <button
          type="button"
          className="sidebar-toggle"
          aria-expanded="true"
          aria-label="Hide the alerts list"
          title="Hide the alerts list"
          onClick={onToggle}
        >
          ‹
        </button>
      </h2>
      <ul className="alert-list">
        {items.map((item) => {
          const severity = item.top_signal?.severity;
          const claim = item.top_signal
            ? item.top_signal.claim
            : item.band === 'grey'
              ? `Inconclusive · ${coverageLabel(item.coverage)} checked`
              : item.band
                ? 'No signals reported.'
                : 'Not checked yet.';
          return (
            <li key={item.cui}>
              <button
                type="button"
                className={`alert-item sev-border-${severity ?? 'info'}${
                  item.cui === selectedCui ? ' is-selected' : ''
                }`}
                aria-current={item.cui === selectedCui ? 'true' : undefined}
                title={severity ? `Top signal severity: ${severity}` : undefined}
                onClick={() => onSelect(item.cui)}
              >
                <span className="alert-item-top">
                  <span className="alert-item-name">{item.name}</span>
                  <BandBadge band={item.band} dot />
                </span>
                <span className="alert-item-bottom">
                  <span className="alert-item-claim">{claim}</span>
                  <OriginBadges origin={item.origin} fictional={item.fictional} compact />
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
