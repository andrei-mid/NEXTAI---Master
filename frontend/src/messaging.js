// Analyst-to-analyst messages (MOCK: no messaging API yet). Kept in this browser's storage so
// a demo survives a refresh and switching "Signed in as" shows the other side of a chat.
import { createContext, useContext } from 'react';
import { loadStored, saveStored } from './storage.js';

const STORAGE_KEY = 'verifirm.messages.v1';

/** Saved messages, or [] when there are none. */
export function loadMessages() {
  return loadStored(STORAGE_KEY, []);
}

export function saveMessages(messages) {
  saveStored(STORAGE_KEY, messages);
}

/**
 * { currentId, startChat(personId, alert) } for the signed-in analyst. alert = { cui, name }
 * of the company the conversation is about, or null. null outside the provider.
 */
export const MessagingContext = createContext(null);

export function useMessaging() {
  return useContext(MessagingContext);
}
