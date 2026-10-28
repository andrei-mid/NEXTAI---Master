import { getAnalyst } from '../mock/analysts.js';
import { useMessaging } from '../messaging.js';

/**
 * "Name · username" for a person id from the accounts table; unknown ids are shown as-is.
 * Clicking the name opens a chat with them in Messages, about `alert` ({ cui, name }) if given.
 * mailSubject: also show an "Email" link that opens the mail app addressed to this person.
 */
export default function AnalystName({ id, mailSubject, alert = null }) {
  const analyst = getAnalyst(id);
  const messaging = useMessaging();
  if (!analyst) return <span className="analyst-name">Unknown analyst ({id ?? 'no id'})</span>;

  const canMessage = messaging && id !== messaging.currentId;
  const name = canMessage ? (
    <button
      type="button"
      className="person-link"
      title={`Message ${analyst.name}${alert ? ` about ${alert.name}` : ''}`}
      onClick={() => messaging.startChat(id, alert)}
    >
      {analyst.name}
    </button>
  ) : (
    analyst.name
  );

  return (
    <span className="analyst-name" title={`${analyst.role} · ${analyst.email}`}>
      {name}
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
