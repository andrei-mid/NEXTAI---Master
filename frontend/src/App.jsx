import { useEffect, useState } from 'react';
import { DATA_MODE, getCompanies } from './api.js';
import { sortByCriticality } from './severity.js';
import AlertsSidebar from './components/AlertsSidebar.jsx';
import ReviewPanel from './components/ReviewPanel.jsx';
import CompanyDetail from './components/CompanyDetail.jsx';
import Dashboard from './components/Dashboard.jsx';
import { ANALYSTS } from './mock/analysts.js';

const VIEWS = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'alerts', label: 'Alerts' },
];

export default function App() {
  const [view, setView] = useState('dashboard');
  // Signed-in account (mock: no login yet, the switcher stands in for it).
  const [analystId, setAnalystId] = useState(ANALYSTS[0].id);
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [selectedCui, setSelectedCui] = useState(null);
  // Append-only list of reviews per CUI, kept in memory until the API is connected.
  const [reviews, setReviews] = useState({});

  useEffect(() => {
    getCompanies()
      .then((res) => {
        const sorted = sortByCriticality(res.items);
        setItems(sorted);
        setSelectedCui((current) => current ?? sorted[0]?.cui ?? null);
      })
      .catch(setError);
  }, []);

  const selected = items.find((c) => c.cui === selectedCui);

  function addReview(cui, review) {
    setReviews((prev) => ({ ...prev, [cui]: [...(prev[cui] ?? []), review] }));
  }

  function openCompany(cui) {
    setSelectedCui(cui);
    setView('alerts');
  }

  return (
    <>
      <header className="topbar">
        <div className="topbar-left">
          <span className="brand">verifirm</span>
          <nav className="menu" aria-label="Main menu">
            {VIEWS.map((v) => (
              <button
                key={v.key}
                type="button"
                className={`menu-item${view === v.key ? ' is-active' : ''}`}
                aria-current={view === v.key ? 'page' : undefined}
                onClick={() => setView(v.key)}
              >
                {v.label}
              </button>
            ))}
          </nav>
        </div>
        <div className="topbar-right">
          {DATA_MODE === 'api' ? (
            <span className="pill pill-outcome">Live API</span>
          ) : (
            <span className="pill pill-mock">MOCK DATA</span>
          )}
          <label className="account">
            <span className="muted small">Signed in as</span>
            <select value={analystId} onChange={(e) => setAnalystId(e.target.value)}>
              {ANALYSTS.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} ({a.role})
                </option>
              ))}
            </select>
            <span className="pill pill-mock pill-xs" title="Mock accounts, no real login yet">
              MOCK
            </span>
          </label>
        </div>
      </header>

      {view === 'dashboard' ? (
        <main className="content dashboard-page">
          {error && <div className="card source-missing">Could not load companies: {error.message}</div>}
          <Dashboard items={items} onOpenCompany={openCompany} />
        </main>
      ) : (
        <div className="shell">
          <AlertsSidebar items={items} selectedCui={selectedCui} onSelect={setSelectedCui} />

          <main className="content">
            <p className="tagline">Prototype · a human analyst decides</p>
            {error && <div className="card source-missing">Could not load companies: {error.message}</div>}
            {selected && (
              <CompanyDetail
                key={selected.cui}
                item={selected}
                sessionReviews={reviews[selected.cui] ?? []}
                analystId={analystId}
              />
            )}
          </main>

          {selected && (
            <ReviewPanel
              key={selected.cui}
              company={selected}
              analystId={analystId}
              history={reviews[selected.cui] ?? []}
              onSubmit={(review) => addReview(selected.cui, review)}
            />
          )}
        </div>
      )}
    </>
  );
}
