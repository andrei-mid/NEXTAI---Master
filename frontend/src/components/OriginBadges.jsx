/**
 * Where a company's data comes from, plus whether the company itself is fictional.
 *  - origin "ui-mock": invented in the frontend mockup -> FICTIV
 *  - origin "backend": served by the API (or its fixtures) -> BACKEND DATA,
 *    plus FICTIV when the backend marks it fictional (team rule: never hide FICTIV),
 *    or REAL when it is a real company.
 * compact: only FICTIV or REAL (for tight lists; the full set is on the company page).
 */
export default function OriginBadges({ origin, fictional, compact = false }) {
  if (compact) {
    return origin === 'ui-mock' || fictional ? (
      <span className="pill pill-fictiv pill-xs" title="Made-up company">
        FICTIV
      </span>
    ) : (
      <span className="pill pill-real pill-xs" title="A real company">
        REAL
      </span>
    );
  }
  if (origin === 'ui-mock') {
    return (
      <span className="pill pill-fictiv" title="Made up in the frontend mockup">
        FICTIV
      </span>
    );
  }
  return (
    <>
      <span className="pill pill-backend" title="Data served by the backend">
        BACKEND DATA
      </span>
      {fictional ? (
        <span className="pill pill-fictiv" title="The backend marks this company as fictional">
          FICTIV
        </span>
      ) : (
        <span className="pill pill-real" title="A real company">
          REAL
        </span>
      )}
    </>
  );
}
