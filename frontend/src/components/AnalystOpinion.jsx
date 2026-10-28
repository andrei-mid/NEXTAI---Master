import { formatUtc } from '../format.js';
import { severityRank } from '../severity.js';

const CATEGORY = {
  cross_source_mismatch: 'Sources disagree',
  financial_inconsistency: 'Numbers',
  suspicious_change: 'Change',
  data_gap: 'Data gap',
  other: 'Other',
};

/**
 * GET /companies/{cui}/analyst-opinion: the AI analyst's educated opinion, collapsed by default.
 * Always next to the official score, never instead of it, and the disclaimer is always visible
 * (docs/DECISIONS.md, "AI analyst opinion"). undefined = loading, null = none yet (404).
 * `invented`: a UI-mock company, which has no dossier at all.
 */
export default function AnalystOpinion({ opinion, invented = false }) {
  if (invented) {
    return (
      <section className="card">
        <h3>AI analyst opinion</h3>
        <p className="muted">
          Not available for this company: it is invented for the UI mockup, so it has no
          official-source dossier (ANAF, ONRC, balance sheets) for the AI analyst to read.
        </p>
      </section>
    );
  }
  if (opinion === undefined) {
    return (
      <section className="card">
        <h3>AI analyst opinion</h3>
        <p className="muted">Loading…</p>
      </section>
    );
  }
  if (opinion === null) {
    return (
      <section className="card">
        <h3>AI analyst opinion</h3>
        <p className="muted">
          Not available yet: no check of this company has run with the AI analyst (it needs an LLM
          key on the server). The official score above is unaffected.
        </p>
      </section>
    );
  }

  const flags = [...opinion.flags].sort((a, b) => severityRank(a.severity) - severityRank(b.severity));

  return (
    <details className="card analyst-opinion">
      <summary>
        <span className="analyst-title">AI analyst opinion</span>
        <span className="pill pill-proposal">AI · to be confirmed</span>
        {opinion.origin === 'example' && <span className="pill pill-mock">EXAMPLE</span>}
        <span className="analyst-scores">
          Opinion <strong>{opinion.opinion_score ?? '—'}</strong>/100
          <span className="muted">
            {' '}
            · official {opinion.official_score ?? '—'} ({opinion.official_band})
          </span>
        </span>
        <span className="analyst-disclaimer">{opinion.disclaimer}</span>
      </summary>

      <div className="analyst-body">
        <p>{opinion.explanation}</p>

        {flags.length === 0 ? (
          <p className="muted">The AI analyst raised no flag that its evidence could back.</p>
        ) : (
          <ul className="claims">
            {flags.map((f) => (
              <li key={f.title + f.claim}>
                <details
                  className="claim"
                  style={{ borderLeftColor: `var(--sev-${f.severity}, var(--sev-info))` }}
                >
                  <summary>
                    <span className="claim-component">{CATEGORY[f.category] ?? f.category}</span>
                    <span className="claim-title">{f.title}</span>
                    <span className={`pill pill-xs sev-${f.severity}`}>{f.severity}</span>
                  </summary>
                  <div className="claim-body">
                    <p className="claim-text">{f.claim}</p>
                    <table className="analyst-evidence">
                      <caption className="muted small">
                        Evidence in the company dossier (checked by code)
                      </caption>
                      <tbody>
                        {f.evidence.map((e) => (
                          <tr key={e.path}>
                            <td>
                              <code>{e.path}</code>
                            </td>
                            <td>{e.value}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              </li>
            ))}
          </ul>
        )}

        {opinion.rejected?.length > 0 && (
          <details className="analyst-rejected">
            <summary className="muted small">
              {opinion.rejected.length} AI flag{opinion.rejected.length > 1 ? 's' : ''} removed:
              the evidence did not check out
            </summary>
            <ul>
              {opinion.rejected.map((r) => (
                <li key={r.flag.title + r.reason} className="small">
                  <strong>{r.flag.title}</strong>: <span className="muted">{r.reason}</span>
                </li>
              ))}
            </ul>
          </details>
        )}

        <p className="muted small">
          {opinion.model ?? 'unknown model'} · {formatUtc(opinion.generated_at)} · The opinion never
          changes the official score or band.
        </p>
      </div>
    </details>
  );
}
