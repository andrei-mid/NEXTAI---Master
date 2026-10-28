import { getAnalyst } from '../mock/analysts.js';

/**
 * "Name · username" for an analyst id from the accounts table; unknown ids are shown as-is.
 * mailSubject: also show an "Email" link that opens the mail app addressed to this analyst.
 */
export default function AnalystName({ id, mailSubject }) {
  const analyst = getAnalyst(id);
  if (!analyst) return <span className="analyst-name">Unknown analyst ({id ?? 'no id'})</span>;
  return (
    <span className="analyst-name" title={`${analyst.role} · ${analyst.email}`}>
      {analyst.name}
      {analyst.username && <span className="muted"> · {analyst.username}</span>}
      {mailSubject && (
        <a
          className="mail-link"
          href={`mailto:${analyst.email}?subject=${encodeURIComponent(mailSubject)}`}
          title={`Email ${analyst.name} (${analyst.email})`}
        >
          ✉ Email
        </a>
      )}
    </span>
  );
}
