# Sections: draft

A draft, not settled. It records what Films from the South publishes about
its themes and competitions, and proposes how Entr'acte could group the
programme by them and let a User take on a whole one. Words follow
[GLOSSARY.md](../../../GLOSSARY.md).

## What the source says (2026 programme, read 2026-10-23)

- The juries page names three prizes: Hovedkonkurranse (Sølvspeilet),
  Dok:Sør and Publikumsprisen. No film page says which of the first two it
  is in yet.
- 61 of 91 film pages carry a badge: "Denne filmen konkurrerer om
  publikumsprisen". This is the only section published as data today.
- The programme's "Hele programmet" view has one heading so far,
  Åpningsfilm. It may fill up closer to the festival.
- Japan is this year's focus country, but only Event text says so ("Japansk
  dag"). Programme cards carry genres and countries as data (`data-genre`,
  `data-country`), several per film.

So themes are thin in the source today and may grow. Genres and countries
are facets for filtering, not themes a festival chose.

## Proposal

A Section is a Curation published by a Festival, filled by its
ProgrammeSource at ingestion rather than by a Curator: a name, an optional
description, and its Programme Entries in the Festival's order.
Re-ingestion updates it like other festival data. Curator-made Curations
(step 5) are the same concept with another publisher, so nothing here is
thrown away.

On the web, the Programme gets the Sections beside the days, and a Section
page lists its films with the same rows. Taking on a Section sets Interest
More for each of its films that has none yet, as one batch in the tray, so
it works with today's Preferences and needs no new item. When step 5 adds
curation weight and the adopt-a-Curation item, Taking on switches to that.

Genre becomes a filter on the Programme, read from the details already
stored; it never becomes a Section.

## Open questions

1. Is a festival section a Curation (as above), or its own concept?
2. Taking on a Section: Interest More for each film (works now), Film
   Commitments for the chosen ones (the spec's Suggested Schedule), or wait
   for curation weight?
3. Scrape Sections now, with only the audience award to show, or wait until
   the competitions are marked?
4. Genre filter on the Programme: wanted?
