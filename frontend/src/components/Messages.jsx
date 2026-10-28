import { useEffect, useRef, useState } from 'react';
import { ANALYSTS, RELATIONSHIP_MANAGERS, getAnalyst } from '../mock/analysts.js';
import { formatUtc } from '../format.js';

const PEOPLE = [...ANALYSTS, ...RELATIONSHIP_MANAGERS];

const between = (m, a, b) => (m.from === a && m.to === b) || (m.from === b && m.to === a);

/** The company a message is about, with a way to open it in Alerts. */
function AlertChip({ alert, onOpen, onRemove }) {
  return (
    <span className="alert-chip">
      <span className="alert-chip-label">Alert</span>
      <span className="alert-chip-name">{alert.name}</span>
      {onOpen && (
        <button type="button" className="btn-link" onClick={() => onOpen(alert.cui)}>
          Open alert →
        </button>
      )}
      {onRemove && (
        <button type="button" className="chip-remove" aria-label="Remove alert" onClick={onRemove}>
          ✕
        </button>
      )}
    </span>
  );
}

/**
 * Chats between the signed-in analyst and other people. Each message can carry the alert
 * (company) it is about; the recipient opens it from the message.
 */
export default function Messages({
  messages,
  currentId,
  activeId,
  onSelectPerson,
  draftAlert,
  onClearDraftAlert,
  onSend,
  onOpenAlert,
  onMarkRead,
}) {
  const [text, setText] = useState('');
  const threadEnd = useRef(null);

  const mine = messages.filter((m) => m.from === currentId || m.to === currentId);
  // Conversations: everyone I have messages with, plus the person I just opened a chat with.
  const partnerIds = [...new Set(mine.map((m) => (m.from === currentId ? m.to : m.from)))];
  if (activeId && !partnerIds.includes(activeId)) partnerIds.unshift(activeId);
  const conversations = partnerIds
    .map((id) => {
      const thread = mine.filter((m) => between(m, currentId, id));
      return {
        id,
        last: thread[thread.length - 1],
        unread: thread.filter((m) => m.to === currentId && !m.read).length,
      };
    })
    .sort((a, b) => (b.last?.sent_at ?? '9').localeCompare(a.last?.sent_at ?? '9'));

  const thread = activeId ? mine.filter((m) => between(m, currentId, activeId)) : [];
  const active = getAnalyst(activeId);

  useEffect(() => {
    if (activeId) onMarkRead(activeId);
    threadEnd.current?.scrollIntoView({ block: 'nearest' });
  }, [activeId, thread.length]); // eslint-disable-line react-hooks/exhaustive-deps

  function send(event) {
    event.preventDefault();
    if (!text.trim() || !activeId) return;
    onSend(activeId, text.trim(), draftAlert);
    setText('');
  }

  return (
    <div className="messages">
      <aside className="conversations" aria-label="Conversations">
        <label className="new-chat">
          <span className="review-label">New message to</span>
          <select value="" onChange={(e) => e.target.value && onSelectPerson(e.target.value)}>
            <option value="">Choose a person…</option>
            {PEOPLE.filter((p) => p.id !== currentId).map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.role})
              </option>
            ))}
          </select>
        </label>

        {conversations.length === 0 ? (
          <p className="muted small">No conversations yet. Click an analyst's name to start one.</p>
        ) : (
          <ul className="conversation-list">
            {conversations.map((c) => {
              const person = getAnalyst(c.id);
              return (
                <li key={c.id}>
                  <button
                    type="button"
                    className={`conversation${c.id === activeId ? ' is-active' : ''}`}
                    onClick={() => onSelectPerson(c.id)}
                  >
                    <span className="conversation-top">
                      <span className="conversation-name">{person?.name ?? c.id}</span>
                      {c.unread > 0 && <span className="unread-badge">{c.unread}</span>}
                    </span>
                    <span className="conversation-last">
                      {c.last ? c.last.text : 'New conversation'}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </aside>

      <section className="chat card">
        {!active ? (
          <p className="muted">Choose a conversation, or click an analyst's name anywhere in the app.</p>
        ) : (
          <>
            <div className="chat-head">
              <h3>{active.name}</h3>
              <span className="muted small">
                {active.role}
                {active.username ? ` · ${active.username}` : ''}
                {!active.username && ' · no login: reads e-mail only'}
              </span>
            </div>

            <ol className="thread">
              {thread.length === 0 && (
                <li className="muted small">No messages yet. Write the first one below.</li>
              )}
              {thread.map((m) => (
                <li key={m.id} className={`bubble ${m.from === currentId ? 'bubble-me' : 'bubble-them'}`}>
                  {m.alert && <AlertChip alert={m.alert} onOpen={onOpenAlert} />}
                  <p>{m.text}</p>
                  <span className="bubble-meta">
                    {m.from === currentId ? 'You' : getAnalyst(m.from)?.name} · {formatUtc(m.sent_at)}
                  </span>
                </li>
              ))}
              <li ref={threadEnd} aria-hidden="true" />
            </ol>

            <form className="composer" onSubmit={send}>
              {draftAlert && <AlertChip alert={draftAlert} onRemove={onClearDraftAlert} />}
              <div className="composer-row">
                <textarea
                  rows={2}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) send(e);
                  }}
                  placeholder={`Message ${active.name}…`}
                  aria-label={`Message ${active.name}`}
                />
                <button type="submit" className="btn btn-primary" disabled={!text.trim()}>
                  Send
                </button>
              </div>
            </form>
          </>
        )}
      </section>
    </div>
  );
}
