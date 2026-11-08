# BrickMatch UI reference

## Source and scope

Source: `Brand guide lines.html`, a SingleFile snapshot of the LEGO India Gift Finder at `https://lego.in/pages/gift-finder`, saved 8 November 2026. This is a page reference, not a comprehensive brand manual. Values below were extracted from its CSS and HTML. They are not guesses based on LEGO's general visual identity.

Only the initial finder screen is preserved. `#page2`, `#page3`, and `#page4` are empty in the snapshot; their interactions and card designs cannot be recovered. Do not claim to have replicated unseen screens.

## Exact reference tokens

| Role | Value | Source selector |
| --- | --- | --- |
| Header yellow | `#ffd500` | `.kdscom-header` |
| Page background | `#ffffff` | `html,body` |
| Body text | `#000000` | `html,body` |
| Primary action | `#0058e6` | `.Gift_finder .next-button` |
| Primary hover | `#0041b8` | `.Gift_finder .next-button:hover` |
| Standard link | `#005ad2` | `a` |
| Link hover | `#001839` | `a:hover` |
| Hero blue | `#006fe3` | `.heading_fisrt` (source spelling) |
| Hero pink | `#f03167` | `.heading_second` |
| Hero green | `#00a843` | `.heading_third` |
| Hero purple | `#861ee3` | `.heading2_forth` |
| Hero orange | `#e96f14` | `.heading2_fifth` |
| Input border | `#bfbfbf` | `input` |
| Footer background | `#111111` | `.custom-footer` |
| Footer pill background | `#f4f4f4` | `.footer-country` |

The source uses **Cera Pro** throughout, with embedded font faces at weights 400, 500, 700, and 900. Body text is 18px, weight 400, line-height 1.6, and zero letter spacing. Ordinary headings use weight 800 and line-height 1.2; h1/h2 are 28.32px and h3 is 24px. General buttons use weight 600.

The opening hero uses 80px text, 80px line-height, weight 600, -3px tracking, 50% width, centered. At widths up to 768px it changes to 40px/50px, -1px tracking, and 90% width. A later max-480px override increases this to 52px/52px. This counterintuitive narrow-screen increase is in the source; use a fluid size for BrickMatch if it causes overflow, and document that adaptation.

Primary buttons have 25px corners, 18px text, weight 500, padding 12px 30px, a 0.2-second background transition, and white text. Disabled buttons use opacity 0.5 and a not-allowed cursor. General buttons have a 170px minimum width. Inputs have 4px corners, 12px 15px padding, and a 1px border.

The site content has a 1600px maximum width. Side padding is 30px normally, 50px from 1400px, and 20px below 768px. The yellow header has 30px horizontal padding, a 40px gap, and a 70px maximum height. The hero action sits 60px below the heading. The visual direction is white space, bold centered copy with colorful words, a strong yellow navigation band, and rounded blue actions.

## BrickMatch adaptation decisions

These are implementation recommendations, not rules found in the snapshot:

- Use the BrickMatch AI name and an original simple brick symbol. Keep the independent recommendation product identity clear.
- Use the exact yellow header and blue action colors. Reserve the five hero accents for large decorative words; use dark text for small labels and information.
- Use a short headline such as “Find your next great build” and a primary “Discover sets” action. Maintain generous white space without forcing an extra landing screen before catalog access.
- Use a system sans-serif fallback such as `Arial, sans-serif` until a suitable font asset is available for project use. The captured font files are reference material, not automatically project assets.
- Build product cards with contained images, title, theme, year, piece count, and labeled feedback buttons. Card spacing and layout are new design decisions because the saved finder does not contain results cards.
- Preserve keyboard focus indicators and visible labels; the snapshot's global focus suppression should not be carried into the application. Ensure mobile controls remain usable and test contrast before release.
- Do not reproduce shop checkout, cart, promotions, newsletter, or commercial footer links. The build plan excludes purchasing.

## Implemented web interface

The served interface is a vanilla HTML/CSS/JavaScript single-page app in
`frontend/web/`, mounted by FastAPI at `/`. It has no build step or framework runtime.
Hash routes cover Discover, Swipe, For You, My Taste, Model Lab, and System. The legacy
`frontend/streamlit_app.py` is retained as a reference only and is not served.

Exact source tokens are used for the yellow header (`#ffd500`), primary action
(`#0058e6`), primary hover (`#0041b8`), and the five hero word accents. Small labels and
body copy stay black or neutral; accents are reserved for large display words. The
header is a full-width yellow band, the page background is white, and actions use the
25px source corner radius. Product cards, filters, and tables are original BrickMatch
layouts because the saved finder contains no results screen to copy.

Cera Pro is not bundled. The interface uses a system sans-serif stack, with a fluid
hero that measured 44px at 390px, 61px at 768px, and 92px at 1440px. The source's
counterintuitive sub-480px size increase was not copied; the fluid clamp avoids
overflow. The primary button is 48px tall and navigation links are 42px tall.

Responsive breakpoints are at 1240, 1080, 900, 700, and 520px. Automated browser checks
at 390, 768, 800, and 1440px found no horizontal overflow; the card grid measured 1, 2,
and 5 columns at the narrow, tablet, and wide widths. The navigation scrolls
horizontally on narrow screens while remaining keyboard reachable.

Accessibility handling includes visible focus styles, real labels on every control,
`aria-pressed` feedback buttons, an `aria-live` toast region, a labelled dialog, text
alternatives for icon-only actions, and a `prefers-reduced-motion` path. An automated
Lighthouse audit at 800px returned 1.00 for accessibility, best practices, and SEO with
no failed audits. Image failures fall back to a neutral brick placeholder without
removing the feedback controls. Loading skeletons, empty results, connection errors,
and unavailable-data states are explicit. The interface never invents age, price, or
popularity fields.

The earlier Streamlit guidance is superseded. Streamlit is no longer a runtime
dependency of the product path; install the optional `legacy` extra only if you need to
inspect the old file.

## Open decisions and verification

No user answer is needed to proceed with the reference-based design. Safe defaults are
the supplied colors, independent BrickMatch identity, system font, and an original
responsive catalog layout. Exact Cera Pro typography can be revisited if a usable
licensed asset is provided. Later finder screens cannot be copied from this snapshot.

Verification performed on 8 November 2026: inspected the saved HTML/CSS selectors,
extracted the tokens above, confirmed the empty later finder screens, and compared the
UI requirements in build-plan section 9.4. The built interface was served by the real
API and exercised in a browser at the widths above: routing, filters, pagination,
swipe/undo, profile switching, recommendation signals, preferences, evaluation display,
and system status all rendered. Static assets and image responses were checked over
HTTP. No side-by-side human screenshot comparison against the LEGO page has been made;
the finder snapshot does not contain the screens needed for one.

