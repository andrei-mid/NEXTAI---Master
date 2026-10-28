import { formatUtc } from '../format.js';

/**
 * The source behind one claim. Every claim must have a link the analyst can open.
 * A claim without a link is shown as a warning, never as a normal finding.
 */
export default function SourceLink({ source, evidenceDate }) {
  if (!source?.url) {
    return (
      <div className="source-box source-missing" role="alert">
        <strong>No source link.</strong> Do not rely on this claim until a source is provided.
        {source?.name && <span className="muted small"> (reported by: {source.name})</span>}
      </div>
    );
  }

  return (
    <div className="source-box">
      <span className={`pill source-type source-${source.type}`}>{source.type}</span>
      <a href={source.url} target="_blank" rel="noopener noreferrer">
        {source.name} ↗
      </a>
      <span className="muted small">
        {evidenceDate && <>evidence {evidenceDate} · </>}
        {source.retrieved_at ? `retrieved ${formatUtc(source.retrieved_at)}` : 'retrieval time unknown'}
      </span>
    </div>
  );
}
