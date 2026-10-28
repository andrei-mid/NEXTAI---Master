import { useState } from 'react';
import { mockAlerts } from './mockAlerts.js';
import AlertsSidebar, { sortByCriticality } from './components/AlertsSidebar.jsx';
import ReviewPanel from './components/ReviewPanel.jsx';
import CompanyDetail from './components/CompanyDetail.jsx';

const alerts = sortByCriticality(mockAlerts);

export default function App() {
  const [selectedCui, setSelectedCui] = useState(alerts[0]?.cui ?? null);
  // Append-only list of reviews per CUI, kept in memory until the API is connected.
  const [reviews, setReviews] = useState({});
  const selected = alerts.find((a) => a.cui === selectedCui);

  function addReview(cui, review) {
    setReviews((prev) => ({ ...prev, [cui]: [...(prev[cui] ?? []), review] }));
  }

  return (
    <>
      <header className="topbar">
        <span className="brand">verifirm</span>
        <span className="pill pill-mock">MOCK DATA</span>
      </header>

      <div className="shell">
        <AlertsSidebar items={alerts} selectedCui={selectedCui} onSelect={setSelectedCui} />

        <main className="content">
          <p className="tagline">Prototype · a human analyst decides</p>
          {selected && (
            <CompanyDetail company={selected} sessionReviews={reviews[selected.cui] ?? []} />
          )}
        </main>

        {selected && (
          <ReviewPanel
            key={selected.cui}
            company={selected}
            history={reviews[selected.cui] ?? []}
            onSubmit={(review) => addReview(selected.cui, review)}
          />
        )}
      </div>
    </>
  );
}
