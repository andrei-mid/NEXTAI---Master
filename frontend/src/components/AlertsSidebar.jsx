import BandBadge from './BandBadge.jsx';
import OriginBadges from './OriginBadges.jsx';
import { coverageLabel } from '../format.js';

/** Left sidebar: one card per company (GET /companies item), already sorted by the caller. */
export default function AlertsSidebar({ items, selectedCui, onSelect }) {
  return (
    <aside className="sidebar" aria-label="Company alerts">
      <h2 className="sidebar-title">
        Alerts <span className="sidebar-count">{items.length}</span>
      </h2>
      <ul className="alert-list">
        {items.map((item) => {
          const severity = item.top_signal?.severity;
          return (
            <li key={item.cui}>
              <button
                type="button"
                className={`alert-item sev-border-${severity ?? 'info'}${
                  item.cui === selectedCui ? ' is-selected' : ''
                }`}
                aria-current={item.cui === selectedCui ? 'true' : undefined}
                onClick={() => onSelect(item.cui)}
              >
                <span className="alert-item-top">
                  {severity && <span className={`pill sev-${severity}`}>{severity}</span>}
                  <BandBadge band={item.band} />
                  <OriginBadges origin={item.origin} fictional={item.fictional} />
                </span>
                <span className="alert-item-name">{item.name}</span>
                <span className="alert-item-claim">
                  {item.top_signal
                    ? item.top_signal.claim
                    : item.band
                      ? 'No signals reported.'
                      : 'Not checked yet.'}
                </span>
                <span className="alert-item-meta">
                  CUI {item.cui} · {coverageLabel(item.coverage)}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
