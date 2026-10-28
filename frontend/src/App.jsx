export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>verifirm</h1>
        <p className="tagline">Prototype · a human analyst decides</p>
      </header>

      <main className="card">
        <h2>Setup check</h2>
        <p>If you can see this page with colored buttons, the setup works.</p>
        <div className="button-row">
          <button type="button" className="btn btn-primary">Primary</button>
          <button type="button" className="btn btn-secondary">Secondary</button>
          <button type="button" className="btn btn-danger">Danger</button>
        </div>
      </main>
    </div>
  );
}
