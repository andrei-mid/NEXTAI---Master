# RiskLens dashboard: specification (from the team lead, 2026-10-28)

> Verbatim brief for the new analyst dashboard. **Read `../HANDOFF.md` first**: several points below were
> changed or clarified with the team lead (location, banner wording, Dedeman data, rule ids).
> Visual reference: [`RiskLens-design-reference.html`](RiskLens-design-reference.html) (layout, styles,
> animations and ALL mock data).

---

Citește CLAUDE.md și SOLUTION.md înainte de orice. Respectă „ASK BEFORE DECIDING”: orice alegere care nu e scrisă aici sau acolo → te oprești și mă întrebi.

## Obiectiv
Înlocuiește frontend-ul existent cu un dashboard nou pentru analiști (RiskLens), construit după specificația de mai jos. Frontend-ul NU conține logică de scoring: banda, scorul și acoperirea vin din API (sau din mock-uri care respectă contractul din SOLUTION.md).

## Pasul 0 — Curățenie (cu confirmare)
1. Creează branch-ul `feat/dashboard-v2`.
2. Găsește frontend-ul existent (probabil `apps/web/` sau un export Lovable). Listează-mi exact ce fișiere și foldere vrei să ștergi și ce păstrezi.
3. NU atinge: `apps/api`, `apps/worker`, `packages/*`, `fixtures/` (cele de backend), `infra/`, `docs/`, CLAUDE.md, SOLUTION.md.
4. Așteaptă „ok” de la mine, apoi șterge cu `git rm` într-un commit separat: `chore(web): remove old frontend`.

## Stack (propunere — confirmă cu mine dacă vrei altceva)
Vite + React 18 + TypeScript strict, Tailwind CSS, React Router, TanStack Query, Framer Motion pentru animații, fără bibliotecă de chart-uri (harta de risc se face cu div-uri poziționate absolut). Fonturi Google: Space Grotesk (titluri), Manrope (text), JetBrains Mono (cifre, CUI-uri, cod).
Config: `VITE_API_BASE_URL`, `VITE_USE_MOCKS=1`. Un singur `src/api/client.ts` cu funcții tipate pentru fiecare endpoint din SOLUTION.md; când `VITE_USE_MOCKS=1`, aceleași funcții întorc date din `src/mocks/` cu o mică latență simulată.
Tipurile TS se generează din `docs/schema/*.json` (exportul Pydantic) dacă există; dacă nu, scrie-le manual în `src/types/` și marchează-le TODO pentru sincronizare.

## Design system
Temă dark, aerisită, accente galbene, totul animat.
- Fundal #0B0D10, sidebar #0E1014, carduri #12151A, inset #0F1217 / #0D1015, borduri #1F242C / #2A3039
- Text #EDEEF0, secundar #B7BEC8, muted #8E97A3 (minim 4.5:1 contrast peste tot)
- Accent galben #FACC15 (hover #FDE047), text pe galben #0B0D10. Se folosește pentru: nav activ, butoane primare, focus ring, badge MOCK.
- Benzi: VERDE #22C55E/#4ADE80 · ATENȚIE (= YELLOW din backend) portocaliu #F97316/#FB923C, ca să nu se confunde cu accentul · ROȘU #EF4444/#F87171 · STOP fundal negru, bordură #EF4444, text #FCA5A5 · GRI „date insuficiente” #71717A
- Severități: critic #FF8A8A, ridicat #F87171, mediu #FB923C, scăzut #93C5FD, info #A7B0BC
- Raze 12–28px, padding generos (24–40px), carduri fără umbre grele, fără gradient-uri decorative, fără emoji (iconițe SVG cu linie, ex. lucide-react).
- Animații (Framer Motion): fade-up cu stagger la intrarea în pagină, bule pop-in + plutire lentă, bare care cresc de la 0, puls pe STOP, hover lift pe carduri, toast-uri. Respectă `prefers-reduced-motion`.
- Responsive: sidebar-ul se stivuiește deasupra conținutului pe mobil; tabelele late au scroll orizontal în cutia lor.
- Accesibilitate: butoane/linkuri/inputuri reale, radio și checkbox reale în formular, aria-label pe butoanele cu doar iconiță.
- Limba UI: română.

## Layout
Sidebar (logo „RiskLens · Verificare agentică companii”, nav: Dashboard, Portofoliu, Coada de verificare [badge cu numărul], Aplicație nouă, Surse de date [punct roșu dacă o sursă e căzută], Jurnal audit; jos: card „Sweep nocturn · ultima rulare”). Header: breadcrumb + titlu, căutare globală (nume/CUI → duce în Portofoliu), buton galben „Rulează sweep” cu bară de progres animată și toast la final.

## Ecrane
1. **Dashboard** `/`
   - 4 KPI: companii monitorizate (+ acoperire medie), hazarde active (STOP + ROȘU), așteaptă decizie, expunere în benzi de risc (mil. RON).
   - Bară stivuită cu distribuția pe benzi + legendă.
   - **Harta de risc (cloud chart)**: fiecare companie e o bulă. x = scor de încredere 0–100 (x% = 4 + scor·0.92), y = expunere pe scară log (y% = 6 + (1 − (log10(exp)+0.4)/2.9)·82), diametru 24 + √exp·1.4 (max 48px), culoarea = banda, cifra din bulă = locul în clasament. Fundal cu 3 zone verticale (0–50 roșu, 50–75 portocaliu, 75–100 verde, tint 5%), linii orizontale la 1 / 10 / 100 mil. Hover: scale + eticheta cu numele. Click: selectează bula și afișează sub hartă un card cu detalii + „Deschide raportul”. Chip-uri de filtru pe bandă (cele nefiltrate se estompează la 12%).
   - **Clasament** lângă hartă: toate companiile după scor, click → raport.
   - **Carduri „Potențiale hazarde detectate”**: STOP → ROȘU → ATENȚIE → GRI, apoi scor crescător. Card: chip bandă (punct pulsând la STOP), badge FICTIV, „detectat acum X”, nume, CUI + CAEN, semnalul principal, scor, nr. semnale și câte sunt grave, „Raport →”. Cardul întreg e clicabil → `/companies/:cui`.
2. **Portofoliu** `/portfolio`: tabel (#, companie + CUI, bandă, scor, acoperire bară + „7/8”, expunere, semnal principal, status decizie), chip-uri de filtru, căutare.
3. **Coada de verificare** `/queue`: stânga „Așteaptă decizia ta” (non-VERDE fără decizie, buton „Analizează”), dreapta „Decizii înregistrate”.
4. **Raport companie** `/companies/:cui`, de sus în jos:
   - Header: înapoi, nume, badge FICTIV sau „COMPANIE REALĂ · DATE LIVE”, CUI · Reg. Com. · CAEN, „Sari la decizie”, „Re-verifică acum” (POST /recheck).
   - **Banner verdict AI, foarte mare**: VERDE → „FAVORABIL” cu verde, orice altă bandă → „NEFAVORABIL” cu roșu (banda reală afișată ca chip lângă). Iconiță bifă/X în cerc, inel de scor (conic-gradient), acoperire „85% · 7/8 surse”, nr. semnale ridicate/critice, o frază de motivare (la STOP: regula de auto-stop declanșată + „direcționat către Compliance”), mențiunea „AI-ul recomandă, nu decide”.
   - Fișa de identitate (dl) + scor pe cele 8 componente (bare animate, ponderi 15/20/15/15/15/10/5/5; componentă indisponibilă = bară hașurată gri + motiv).
   - Semnale ordonate după severitate: claim, componentă, sursă, dată, încredere, rule_id, badge-uri MOCK / NEVERIFICAT / AUTO-STOP.
   - Situații financiare 5 ani (cifră de afaceri cu mini-bară, profit, datorii, capitaluri, angajați; negative cu roșu; „—” unde lipsește) + card „Declarat vs. oficial”.
   - Litigii (nr. dosar, obiect, rol, stadiu, severitate) + Rețea (administrator central, firme legate cu status colorat, fiecare clicabilă → raportul ei).
   - Memo AI (badge „VERIFICAT DE CRITIC”) + „Întrebări pentru client”.
   - **Formular decizional analist** (bordură galbenă): 1) decizie — radio carduri: Aprobă / Solicită informații / Escaladează la Compliance / Respinge; 2) acord cu AI: De acord / Parțial / Dezacord; 3) checklist secțiuni verificate (identitate, financiar, semnale, litigii, rețea, documente); 4) re-verificare după 30/90/180/365 zile; 5) motivare, textarea cu minim 20 de caractere și contor. Validare cu mesaj inline. Submit → `POST /companies/{cui}/decision` → card de confirmare + „Modifică decizia”; invalidează coada și portofoliul.
5. **Aplicație nouă** `/new`: input CUI cu validare live (cheia 753217532, ×10 mod 11, 10→0; prefix RO acceptat; 99000xxx acceptat doar cu FIXTURE_MODE → mesaj mov), upload PDF, „Pornește cei 8 agenți” → `POST /applications`, apoi progres live pe agent din SSE `/runs/{id}/events` (bară + status: în așteptare / rulează / ok / ok · mock / indisponibil / timeout). La final: „Deschide raportul”. În mock mode simulează SSE-ul cu un timer.
6. **Surse de date** `/sources`: carduri pe sursă cu tip LIVE / BULK / BATCH / MOCK, limite (ex. ANAF 1 req/s, 100 CUI/request) și ultima sincronizare. Banner „Test de reziliență” cu buton „Simulează căderea Portal Just”: în mock mode, componenta Litigii devine indisponibilă și orice companie VERDE devine ATENȚIE (Dedeman → 7/8 surse). Logica asta stă DOAR în stratul de mock, nu în componente.
7. **Jurnal audit** `/audit`: listă append-only (timp, actor, acțiune, punct colorat). Deschiderea unui raport și fiecare decizie adaugă o intrare.

## Mock data (`src/mocks/`)
Folosește exact companiile din secțiunea 8 a raportului de arhitectură (Dedeman 2816464 real; Aurora, Zephyria, Brunaldo, Kestrel, Orvanto, Pelinor, Vantiro, Mirelda, Calbrona fictive) cu datele de acolo (financiare, dosare, rețeaua lui Ionel Fictivescu, declarat vs. ANAF, memo-uri, întrebări). Adaugă 10 firme fictive (CUI 99000104–99000198, nume evident inventate, `fictional: true`) ca harta să fie populată. Scoruri pe componente [identitate, financiar, fiscal, litigii, rețea, sancțiuni, media, prezență] (null = indisponibil):
dedeman [100,95,100,90,100,100,95,100] VERDE exp 250 · aurora [100,92,100,100,100,100,100,85] VERDE 2.5 · zephyria [50,20,40,85,30,100,85,70] ROȘU 12 · brunaldo [85,25,30,30,85,100,85,90] ROȘU 18 · kestrel [60,15,40,0,40,100,80,50] STOP 2.1 · orvanto [0,null,40,70,40,100,90,40] STOP 1 · pelinor [70,20,35,0,45,100,85,60] STOP 6.4 · vantiro [0,40,30,80,45,100,90,50] STOP 3.2 · mirelda [70,65,75,90,40,100,100,60] ATENȚIE 1.9 · calbrona [0,30,30,80,50,100,100,40] STOP 0.5 · lumivar [100,88,100,95,100,100,100,90] VERDE 7.8 · norvessa [95,80,95,90,100,100,95,85] VERDE 13 · quintaro [90,70,85,55,90,72,80,90] ATENȚIE 42 · belvento [100,82,90,85,95,100,90,95] VERDE 4 · saltoria [85,55,80,70,85,100,85,80] ATENȚIE 5.3 · drumexa [65,30,35,40,55,100,70,75] ROȘU 48 · fermiola [100,85,95,100,95,100,100,80] VERDE 32 · velorin [90,null,null,null,85,100,null,null] GRI 80 · tarvinia [80,60,70,85,75,100,85,55] ATENȚIE 1.2 · ombrelo [75,25,40,45,70,100,90,70] ROȘU 6
Scorurile și benzile sunt precalculate în fișierele mock (scor = media ponderată pe componentele disponibile), NU calculate în componente. Expunerile sunt valori demo — marchează-le ca atare în UI.
Regulile din CLAUDE.md rămân valabile: badge-uri MOCK / FICTIV / NEVERIFICAT vizibile, URL-uri .example, nicio cifră inventată pentru firma reală în afară de cele din raport.

## Structură
src/app (router, layout), src/pages/*, src/components/{dashboard,report,ui}, src/api, src/mocks, src/types, src/lib/cui.ts, src/styles/tokens.ts (culorile de mai sus ca tokeni Tailwind).

## Livrare
- Commit-uri mici, convenționale, pe ecran.
- Teste Vitest pentru `cui.ts` (2816464 valid, 2816465 invalid, RO2816464 valid, 99000025 doar în fixture mode) și pentru maparea bandă → verdict.
- `npm run build` și `npm run lint` fără erori.
- La final: un README scurt în `apps/web` cu cum se rulează cu mock-uri și cu backend-ul real, plus lista întrebărilor deschise pe care le-ai pus în docs/DECISIONS.md la „PENDING”.

Începe cu Pasul 0 și listează-mi ambiguitățile înainte să scrii cod.
