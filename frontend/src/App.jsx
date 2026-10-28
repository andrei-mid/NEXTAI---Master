import { useEffect, useState } from 'react';
import { DATA_MODE, SNAPSHOT_TAKEN_AT, getCompanies } from './api.js';
import { formatUtc } from './format.js';
import { sortByCriticality } from './severity.js';
import AlertsSidebar from './components/AlertsSidebar.jsx';
import ReviewPanel from './components/ReviewPanel.jsx';
import CompanyDetail from './components/CompanyDetail.jsx';
import Dashboard from './components/Dashboard.jsx';
import Messages from './components/Messages.jsx';
import { ANALYSTS } from './mock/analysts.js';
import { MessagingContext, loadMessages, saveMessages } from './messaging.js';
import { loadStored, saveStored } from './storage.js';

const REVIEWS_KEY = 'verifirm.reviews.v1';

const VIEWS = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'alerts', label: 'Alerts' },
  { key: 'messages', label: 'Messages' },
];

export default function App() {
  const [view, setView] = useState('dashboard');
  // Signed-in account (mock: no login yet, the switcher stands in for it).
  const [analystId, setAnalystId] = useState(ANALYSTS[0].id);
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [selectedCui, setSelectedCui] = useState(null);
  // Append-only list of reviews per CUI, kept in this browser until the API can store them.
  const [reviews, setReviews] = useState(() => loadStored(REVIEWS_KEY, {}));
  const [messages, setMessages] = useState(loadMessages);
  const [chatWith, setChatWith] = useState(null);
  const [draftAlert, setDraftAlert] = useState(null);

  useEffect(() => {
    getCompanies()
      .then((res) => {
        const sorted = sortByCriticality(res.items);
        setItems(sorted);
        setSelectedCui((current) => current ?? sorted[0]?.cui ?? null);
      })
      .catch(setError);
  }, []);

  useEffect(() => saveMessages(messages), [messages]);
  useEffect(() => saveStored(REVIEWS_KEY, reviews), [reviews]);

  const selected = items.find((c) => c.cui === selectedCui);
  const unread = messages.filter((m) => m.to === analystId && !m.read).length;

  function addReview(cui, review) {
    setReviews((prev) => ({ ...prev, [cui]: [...(prev[cui] ?? []), review] }));
  }

  function openCompany(cui) {
    setSelectedCui(cui);
    setView('alerts');
  }

  function switchAccount(id) {
    setAnalystId(id);
    setChatWith(null);
    setDraftAlert(null);
  }

  /** Open Messages on a chat with personId, with the alert (company) attached to the draft. */
  function startChat(personId, alert) {
    setChatWith(personId);
    setDraftAlert(alert ?? null);
    setView('messages');
  }

  function sendMessage(to, text, alert) {
    const message = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      from: analystId,
      to,
      text,
      alert: alert ?? null,
      sent_at: new Date().toISOString(),
      read: false,
    };
    setMessages((prev) => [...prev, message]);
    setDraftAlert(null);
  }

  function markRead(fromId) {
    setMessages((prev) =>
      prev.some((m) => m.from === fromId && m.to === analystId && !m.read)
        ? prev.map((m) => (m.from === fromId && m.to === analystId ? { ...m, read: true } : m))
        : prev,
    );
  }

  return (
    <MessagingContext.Provider value={{ currentId: analystId, startChat }}>
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
                {v.key === 'messages' && unread > 0 && (
                  <span className="unread-badge" aria-label={`${unread} unread`}>
                    {unread}
                  </span>
                )}
              </button>
            ))}
          </nav>
        </div>
        <div className="topbar-right">
          {DATA_MODE === 'api' ? (
            <span className="pill pill-outcome">Live API</span>
          ) : DATA_MODE === 'snapshot' ? (
            <span className="pill pill-outcome" title="Saved copy of the API's data, read offline">
              Snapshot · {formatUtc(SNAPSHOT_TAKEN_AT)}
            </span>
          ) : (
            <span className="pill pill-mock">MOCK DATA</span>
          )}
          <label className="account">
            <span className="muted small">Signed in as</span>
            <select value={analystId} onChange={(e) => switchAccount(e.target.value)}>
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

      {view === 'dashboard' && (
        <main className="content dashboard-page">
          {error && <div className="card source-missing">Could not load companies: {error.message}</div>}
          <Dashboard items={items} onOpenCompany={openCompany} />
        </main>
      )}

      {view === 'messages' && (
        <main className="content dashboard-page">
          <Messages
            messages={messages}
            currentId={analystId}
            activeId={chatWith}
            onSelectPerson={(id) => {
              setChatWith(id);
              setDraftAlert(null);
            }}
            draftAlert={draftAlert}
            onClearDraftAlert={() => setDraftAlert(null)}
            onSend={sendMessage}
            onOpenAlert={openCompany}
            onMarkRead={markRead}
          />
        </main>
      )}

      {view === 'alerts' && (
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
                messages={messages.filter((m) => m.alert?.cui === selected.cui)}
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
    </MessagingContext.Provider>
  );
}
