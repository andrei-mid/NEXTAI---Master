/**
 * Where a company's data comes from, plus whether the company itself is fictional.
 *  - origin "ui-mock": invented in the frontend mockup -> FICTIV
 *  - origin "backend": served by the API (or its fixtures) -> BACKEND DATA,
 *    plus FICTIV when the backend marks it fictional (team rule: never hide FICTIV),
 *    or REAL when it is a real company.
 */
export default function OriginBadges({ origin, fictional }) {
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
