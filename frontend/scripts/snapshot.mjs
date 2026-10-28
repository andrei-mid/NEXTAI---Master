// Saves what the backend API returns into snapshot/data.json, so the site can show the same
// data offline (no server, no tunnel). Run: npm run snapshot
//
// The URL comes from VITE_API_URL in .env.local (or the first argument).
// snapshot/ is git-ignored: it can hold real-company figures, which are never committed.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const outFile = path.join(root, 'snapshot', 'data.json');

function apiUrlFromEnvFile() {
  const file = path.join(root, '.env.local');
  if (!fs.existsSync(file)) return undefined;
  const line = fs
    .readFileSync(file, 'utf8')
    .split(/\r?\n/)
    .find((l) => l.trim().startsWith('VITE_API_URL='));
  return line?.split('=')[1]?.trim() || undefined;
}

const apiUrl = (process.argv[2] ?? apiUrlFromEnvFile())?.replace(/\/$/, '');
if (!apiUrl) {
  console.error('No API URL. Set VITE_API_URL in .env.local or pass it: npm run snapshot -- <url>');
  process.exit(1);
}

/** GET as JSON; null on 404 (no data yet), an error for anything else. */
async function get(p) {
  const res = await fetch(`${apiUrl}${p}`, { signal: AbortSignal.timeout(60_000) });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API error ${res.status} on ${p}`);
  return res.json();
}

console.log(`Reading ${apiUrl} ...`);
const list = await get('/companies?page_size=200');
const companies = {};

for (const item of list.items) {
  process.stdout.write(`  ${item.cui} ${item.name} ... `);
  const [company, signals, history] = await Promise.all([
    get(`/companies/${item.cui}`),
    get(`/companies/${item.cui}/signals`),
    get(`/companies/${item.cui}/history`),
  ]);
  companies[item.cui] = { company, signals, history };
  console.log('ok');
}

const snapshot = { taken_at: new Date().toISOString(), api_url: apiUrl, list, companies };
fs.mkdirSync(path.dirname(outFile), { recursive: true });
fs.writeFileSync(outFile, JSON.stringify(snapshot, null, 2));
console.log(`Saved ${list.items.length} companies to snapshot/data.json`);
