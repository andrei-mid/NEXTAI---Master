const KNOWN_BANDS = ['stop', 'red', 'yellow', 'green', 'grey'];

/** Band from the API, shown as-is. null = never checked; unknown values get a neutral style. */
export default function BandBadge({ band }) {
  if (!band) return <span className="pill band-none">not checked</span>;
  const cls = KNOWN_BANDS.includes(band) ? `band-${band}` : 'band-none';
  return <span className={`pill ${cls}`}>{band}</span>;
}
