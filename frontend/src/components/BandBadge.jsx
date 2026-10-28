const KNOWN_BANDS = ['stop', 'red', 'yellow', 'green', 'grey'];

/**
 * Band from the API, shown as-is. null = never checked; unknown values get a neutral style.
 * dot: a coloured dot instead of the word (STOP keeps its word); the band is in the tooltip
 * and for screen readers.
 */
export default function BandBadge({ band, dot = false }) {
  const label = band ?? 'not checked';
  const cls = band && KNOWN_BANDS.includes(band) ? `band-${band}` : 'band-none';
  if (dot && band !== 'stop') {
    return <span className={`band-dot ${cls}`} title={label} role="img" aria-label={`Band: ${label}`} />;
  }
  return <span className={`pill ${cls}`}>{label}</span>;
}
