# Web concepts: design plan

Subject: planning a week at Films from the South (Oslo). One person, many
films, four or five venues. The job: see the week, change it, accept it.

## Tokens

Colour. A silver screen, black ink, one stamp of ultramarine.

| Name   | Light     | Dark      | Use                                  |
| ------ | --------- | --------- | ------------------------------------ |
| screen | `#E9EBEC` | `#000000` | background                           |
| ink    | `#000000` | `#E9EBEC` | text, every border                   |
| grain  | `#5F656B` | `#8A9096` | secondary text, withdrawn, excluded  |
| haze   | `#D5D9DC` | `#1C1E20` | hover, timeline track                |
| stamp  | `#2323C8` | `#8C8CFF` | yours: committed, ticket, focus ring |

Type. Two serifs that never swap roles.

- Bodoni Moda (didone, optical size 96): film titles only. Huge, tight,
  line-height 0.88. A title is the poster.
- Newsreader: everything else. 17px body, tabular lining figures for times.
- Scale, perfect fourth: 13, 17, 23, 30, 40, 53, 71, 95, 127.

Borders. 1px ink, radius 0. Rules separate rows; boxes only for controls.

Icons. Phosphor, light weight, 18px. No icon without a label or tooltip.

## Layout

Home: the wordmark across the top, its apostrophe in stamp, dropping in
once on load. One line of copy. Then the Festivals as a credits roll,
name left, dates right; past ones in grain.

Header: the app icon at left, back to Home. On wide screens the Festival's
name follows it; on phones the icon stands alone.

Programme: a credits roll. One column of titles, each on its own rule.
Times sit to the right, small. Days run across the top.

```
Films from the South          ◷  ⇄  ◌
9 10 11 12 13 14 15 16 17 18
──────────────────────────────────────────
Sirāt                      Fri 18:00 Vika   + ×
                           Sun 21:15 Saga   + ×
──────────────────────────────────────────
Sentimental Value          ...
```

Film: the title fills the width. Below, the screenings as rows.

Schedule: one row per Festival Day. A big day numeral at left, then a track from 10 to
24 with one block per screening, width by running time.

```
10 ┃ ▭▭▭ Sirāt ▭▭▭      ▭▭ Magellan ▭▭
11 ┃        ▭▭▭▭ Dry Leaf ▭▭▭▭
```

Draft: the diff. `+` and `−` rows, the score change, Accept and Discard.

Compare: two titles, stacked, as large as they fit. Tap the one you would
rather see. The other fades to grain. This is the one motion moment.

Tray: a bar along the bottom holding the pending Change Set. Count, list,
Solve.

Alignment: left, ragged right. Times and numerals right-aligned in their
column.

## Principles

1. Titles are the only loud thing. Everything else whispers in Newsreader.
2. Ultramarine means "yours". Nothing else gets colour.
3. One word where one word will do. Icons carry verbs; tooltips name them.
4. Days are a real sequence, so they are numbered. Nothing else is.

## Review against the brief

- Considered Kodak yellow as the accent. Dropped it: a highlighter yellow
  reads as generic "marker". Ultramarine reads as an ink stamp on a ticket.
- Considered the week as day columns (a calendar). Changed to day rows with
  a horizontal track: it reads like a strip of film and uses wide screens.
- Sharp borders and serifs are the brief's own words, so hairlines and zero
  radius stay. Dense newspaper columns do not: one column, generous rows.
- No mono, no all-caps labels, no eyebrows, no middle-dot meta strings.

## Architecture

Ports and adapters, like the backend.

- `domain/`: types and pure functions (time in the festival's zone, the
  Change Set reducer, timeline layout). No React.
- `domain/ports.ts`: interfaces the app needs: programme, planning, session.
- `adapters/graphql`: urql core with gql.tada types from `../schema.graphql`.
- `adapters/memory`: seeded sample data and a greedy fake solver, so the
  concepts run without a server.
- `adapters/browser`: the token in localStorage.
- `app/`: hooks that turn ports into view models and actions.
- `views/`: props in, JSX out. No hooks, no fetching.
- `routes/`: call one app hook, render one view.

Pick the adapter with `VITE_ADAPTER=memory|graphql` (default `memory`).
