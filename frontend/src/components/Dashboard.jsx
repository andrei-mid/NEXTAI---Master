import { useState } from 'react';

// Band order and colours for the chart (checked for colour-blind separation on the dark
// surface; every segment also carries a label and a count, so colour is never alone).
const BANDS = [
  { key: 'stop', label: 'STOP', color: '#e5484d' },
  { key: 'red', label: 'Red', color: '#ff8f5a' },
  { key: 'yellow', label: 'Yellow', color: '#ffd25c' },
  { key: 'green', label: 'Green · nothing flagged', color: '#6fdc9b' },
  // Includes the "grey" band and companies the API has not scored yet.
  { key: 'none', label: 'Grey · not checked yet', color: '#73767d' },
];

const RADIUS = 80;
const STROKE = 28;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
const GAP = 2; // px of surface between segments

function countByBand(items) {
  const counts = Object.fromEntries(BANDS.map((b) => [b.key, 0]));
  for (const item of items) {
    const key = item.band && item.band in counts ? item.band : 'none';
    counts[key] += 1;
  }
  return counts;
}

function percent(n, total) {
  return total === 0 ? 0 : Math.round((n / total) * 100);
}

/** Donut of the portfolio by band. Hovering a segment or legend row shows its numbers. */
function BandDonut({ counts, total }) {
  const [hovered, setHovered] = useState(null);
  const active = BANDS.find((b) => b.key === hovered);

  let offset = 0;
  const segments = BANDS.filter((b) => counts[b.key] > 0).map((b) => {
    const length = (counts[b.key] / total) * CIRCUMFERENCE;
    const seg = { ...b, length, offset };
    offset += length;
    return seg;
  });
  const single = segments.length === 1;

  return (
    <div className="donut-wrap">
      <svg
        className="donut"
        viewBox="0 0 200 200"
        role="img"
        aria-label={BANDS.map((b) => `${b.label}: ${counts[b.key]}`).join(', ')}
      >
        <circle cx="100" cy="100" r={RADIUS} fill="none" stroke="var(--border)" strokeWidth={STROKE} />
        {segments.map((s) => (
          <circle
            key={s.key}
            cx="100"
            cy="100"
            r={RADIUS}
            fill="none"
            stroke={s.color}
            strokeWidth={hovered === s.key ? STROKE + 6 : STROKE}
            strokeDasharray={`${single ? s.length : Math.max(s.length - GAP, 0.5)} ${CIRCUMFERENCE}`}
            strokeDashoffset={-s.offset}
            transform="rotate(-90 100 100)"
            opacity={hovered && hovered !== s.key ? 0.35 : 1}
            onMouseEnter={() => setHovered(s.key)}
            onMouseLeave={() => setHovered(null)}
          >
            <title>{`${s.label}: ${counts[s.key]} (${percent(counts[s.key], total)}%)`}</title>
          </circle>
        ))}
        <text x="100" y="96" textAnchor="middle" className="donut-value">
          {active ? counts[active.key] : total}
        </text>
        <text x="100" y="118" textAnchor="middle" className="donut-caption">
          {active ? `${active.label.split(' ·')[0]} · ${percent(counts[active.key], total)}%` : 'companies'}
        </text>
      </svg>

      <ul className="donut-legend">
        {BANDS.map((b) => (
          <li
            key={b.key}
            className={hovered === b.key ? 'is-hovered' : undefined}
            onMouseEnter={() => setHovered(b.key)}
            onMouseLeave={() => setHovered(null)}
          >
            <span className="legend-swatch" style={{ background: b.color }} />
            <span className="legend-label">{b.label}</span>
            <span className="legend-count">{counts[b.key]}</span>
            <span className="legend-pct muted small">{percent(counts[b.key], total)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const NEW_WINDOW_HOURS = 24;

function hoursSince(iso, now) {
  return (now - new Date(iso).getTime()) / 3_600_000;
}

function agoLabel(hours) {
  if (hours < 1) return 'less than an hour ago';
  const h = Math.floor(hours);
  if (h < 48) return `${h} ${h === 1 ? 'hour' : 'hours'} ago`;
  return `${Math.floor(h / 24)} days ago`;
}

/**
 * "N new · most recent X ago". The API has no "flag first raised" time, so "new" means the
 * company's latest check finished within the last NEW_WINDOW_HOURS.
 */
function recency(group, now) {
  const checked = group.filter((i) => i.last_checked).map((i) => hoursSince(i.last_checked, now));
  if (checked.length === 0) return null;
  const fresh = checked.filter((h) => h <= NEW_WINDOW_HOURS).length;
  const newest = Math.min(...checked);
  return `${fresh} new in the last ${NEW_WINDOW_HOURS} h · most recent ${agoLabel(newest)}`;
}

/** One headline number with what it means and a way into the Alerts page. */
function SummaryCard({ tone, title, count, detail, hint, group, onOpenCompany }) {
  return (
    <section className={`card summary-card summary-${tone}`}>
      <h3 className="summary-title">{title}</h3>
      <p className="summary-count">{count}</p>
      <p className="summary-detail">{count === 0 ? 'Nothing here right now.' : detail}</p>
      {hint && <p className="muted small">{hint}</p>}
      {group.length > 0 && (
        <button type="button" className="btn-link" onClick={() => onOpenCompany(group[0].cui)}>
          Review in Alerts →
        </button>
      )}
    </section>
  );
}

/** Portfolio overview for the analyst. Counts only what the API returned; no scoring here. */
export default function Dashboard({ items, onOpenCompany }) {
  const counts = countByBand(items);
  const total = items.length;
  const now = Date.now();
  // items arrive sorted by criticality, so group[0] is the most urgent one.
  const urgent = items.filter((i) => i.band === 'stop' || i.band === 'red');
  const postponable = items.filter((i) => i.band === 'yellow');

  return (
    <div className="dashboard">
      <div>
        <h1 className="page-title">Portfolio overview</h1>
        <p className="tagline">
          {total} companies · what the latest checks found. A human analyst decides.
        </p>
      </div>

      <div className="summary-grid">
        <SummaryCard
          tone="urgent"
          title="Urgent attention needed"
          count={urgent.length}
          detail={recency(urgent, now)}
          hint={`${counts.stop} STOP · ${counts.red} red`}
          group={urgent}
          onOpenCompany={onOpenCompany}
        />
        <SummaryCard
          tone="later"
          title="Can be postponed"
          count={postponable.length}
          detail={recency(postponable, now)}
          group={postponable}
          onOpenCompany={onOpenCompany}
        />
      </div>

      <section className="card">
        <h3>Companies by risk band</h3>
        <p className="muted small">
          Green means no flags were found, not that the company was approved.
        </p>
        {total === 0 ? (
          <p className="muted">No companies loaded.</p>
        ) : (
          <BandDonut counts={counts} total={total} />
        )}
      </section>
    </div>
  );
}
