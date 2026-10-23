# Entr’acte: design

Entr’acte plans a film festival for one person: many films, about ten days,
a handful of venues. It shows the festival, helps change the schedule, and
keeps the person on track between screenings. Words follow
[CONTEXT.md](CONTEXT.md); code layout is in [README.md](README.md).

## Character

A good usher: elegant, calm, with the whole house in view. It shows the way
with a small light and a few words, then steps back. It never hurries,
never raises its voice, and never decides for you. So every page opens on
the whole picture, problems are pointed to with one way forward, and
nothing changes until you accept it.

## Brand

The name is the interval between acts; the app lives in the gaps between
screenings. Write `entracte` where an apostrophe is awkward. The wordmark is
Bodoni Moda outlines in ink, with the apostrophe in ultramarine: the
interval, and the usher’s light. The icon is a stage with the curtains
drawn back and that apostrophe hanging in the opening. The voice is brief,
courteous and sure of itself.

## Tokens

| Name   | Light     | Dark      | Use                       |
| ------ | --------- | --------- | ------------------------- |
| screen | `#E9EBEC` | `#000000` | background                |
| ink    | `#000000` | `#E9EBEC` | text, borders             |
| grain  | `#5F656B` | `#8A9096` | secondary, struck, past   |
| haze   | `#D5D9DC` | `#1C1E20` | hover, timeline track     |
| stamp  | `#2323C8` | `#8C8CFF` | yours, and the focus ring |

Dark mode is the auditorium with the lights down.

Bodoni Moda at optical size 96 sets film and festival titles and nothing
else: huge, tight, line-height 0.88. Newsreader sets everything else at
17px with tabular figures. The scale is a perfect fourth from 13 to 127.

Borders are 1px ink with square corners. Rules separate rows; boxes are for
controls. Icons are Phosphor, light, 18px, and always named.

## Rules

Titles are the only loud thing.

Ultramarine means yours: scheduled times, committed titles, tickets,
pending changes, the count of tickets to let go. Nothing else gets colour.
Struck-through grain means excluded or withdrawn; a dashed outline marks a
withdrawn block.

One word where one will do. Buttons say what happens. Problems say what to
do next, empty pages point to the next step, and no id is ever shown.

Days are numbered because they are a sequence. Nothing else is numbered.

Problems are pointed to, never drawn into the schedule: one quiet line
above it, one action.

Changing the schedule and letting go of a ticket are separate. Neither
waits on the other, and neither happens by itself.

## Layout

Rows, not cards: one item per rule, generous space, left aligned and
ragged right. Times and numerals align right in their own column. Wide
screens set a title and its details side by side; phones stack them.

## Pages

Home shows the wordmark, one line of copy, and the festivals as a credits
roll.

The programme is a credits roll too: one title per rule, its screenings
small to the right, the festival days along the top.

```
All  30 31  1  2  3  4  5  6  7  8
──────────────────────────────────────────────
Sirāt                Fri 30  18:00  Vika 2   + ×
                     Mon 2   21:15  Saga 4   + ×
──────────────────────────────────────────────
Sentimental Value    ...
```

The film page lets the title fill the width, with the screenings beneath.

The schedule is one row per festival day: the day’s numeral, then a track
across the schedule’s hours with a block per screening, its width the running
time. It reads like a strip of film. Today is inverted and a thin line marks
now. On phones each day becomes a list with its numeral pinned.

```
30 ┃ ▭ Father Mother… ▭   ▭ Sirāt ▭    ■ Sentimental Value ■
31 ┃      ▭ The Mastermind ▭   ▭ It Was Just… ▭   ▭ The Secret Agent ▭
```

A draft shows what comes in and what goes out, then Accept.

Tickets lists the ones to let go above the ones held.

Compare stacks two titles. Tap the one you would rather see.

Pending changes wait in a tray along the bottom edge.

## Motion

Two moments only: the apostrophe drops into the wordmark once on Home, and
on Compare the title not chosen fades away. Everything else moves only in
answer to a tap, briefly. Reduced motion turns it all off.
