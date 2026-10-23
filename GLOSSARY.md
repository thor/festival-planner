# Festival Planner

Planning which film festival screenings to attend, given travel between venues, personal preferences and curator suggestions.

## Language

### Programme

**Festival**:
A single edition of a film festival, with its own dates, time zone and programme.
_Avoid_: Edition, event

**Festival Series**:
The recurring identity that groups Festivals across years (e.g. "Films from the South").
_Avoid_: Brand, festival (when meaning the recurring identity)

**Film**:
A cinematic work, independent of any festival, identifiable across festivals and external providers.
_Avoid_: Movie, title, work

**Programme Entry**:
A Film as presented in one Festival's programme, carrying the festival-supplied information that is the primary source for display.
_Avoid_: Listing, festival film, catalogue entry

**Screening**:
A single showing of a Programme Entry at a given time and Venue.
_Avoid_: Showing, show, event, film (when meaning a showing)

**Withdrawn**:
A Screening that a Festival's programme no longer lists. It is kept, never offered for scheduling, so anything that referred to it can be flagged. A moved Screening is one Withdrawn Screening plus a new one.
_Avoid_: Cancelled, deleted, removed

**Event**:
Something belonging to a Screening beyond the film itself (e.g. a director talk, an industry debate, an award ceremony), either within the Screening's time or timed on its own. Its kind is free-form, not a fixed category.
_Avoid_: Special notes, special event, Q&A, extra

**Enrichment**:
Supplementary information about a Film from an external provider (e.g. Letterboxd), shown alongside but never replacing festival-supplied information.
_Avoid_: Metadata, extra info

### Places and travel

**Venue**:
A fixed physical place where screenings take place, known in advance of a festival.
_Avoid_: Cinema, location, theatre

**Auditorium**:
The room within a Venue where a Screening takes place, named or numbered by the Venue ("3", "Lillebil"). Optional: not every programme says.
_Avoid_: Room, hall, screen, sal

**Route**:
A precalculated way of travelling from one Venue to another by a given Transport Mode, with its own travel time. There can be several Routes between the same two Venues.
_Avoid_: Travel time, path, leg

**Transport Mode**:
How a Route is travelled, possibly a combination (e.g. walk + e-scooter, walk + bikeshare, bike, e-scooter).
_Avoid_: Travel method, vehicle

### Planning

**User**:
A person who plans their attendance at Festivals.
_Avoid_: Account, attendee, customer

**Schedule**:
A set of Screenings a User intends to attend at one Festival.
_Avoid_: Plan, itinerary, programme

**Active Schedule**:
The User's most recently accepted Schedule for a Festival; at most one per User and Festival. Previously accepted Schedules form the schedule history.
_Avoid_: Current plan, live schedule

**Draft**:
A proposed Schedule not yet accepted. A User may have several Drafts for the same Festival at once.
_Avoid_: Draft plan, proposal, candidate

**Change Set**:
The changes a Draft proposes to a User's commitments, Excluded Programme Entries and Screenings, and Preferences for one Festival. They take effect only when the Draft is accepted.
_Avoid_: Diff, patch, edits

**Stale**:
A Draft whose Change Set was made against an Active Schedule that has since been replaced. A Stale Draft cannot be accepted until it is re-solved against the current Active Schedule.
_Avoid_: Outdated, expired, invalid

**Screening Commitment**:
A User's commitment to attend one specific Screening.
_Avoid_: Pin, booking, will-watch

**Film Commitment**:
A User's commitment to watch a Programme Entry at one of its Screenings, leaving the choice of Screening open. "Film" here means the Programme Entry, not the festival-independent Film.
_Avoid_: Want, wishlist

**Ticket**:
A User's record that they hold a ticket for a Screening, which may still be refundable or exchangeable depending on the Festival.
_Avoid_: Booking, purchase, reservation

**Excluded**:
A Programme Entry or Screening the User does not want scheduled.
_Avoid_: Ignored, hidden, blacklisted

**Comparison**:
A User's statement that they would rather watch one Programme Entry than another.
_Avoid_: Vote, ranking, A/B

**Preferences**:
A User's settings that shape their Schedules for a Festival, such as buffer times (overall and per Venue), the days they can go, weights, Comparisons, Event attendance and Transport Mode.
_Avoid_: Settings, config

### Viewing history

**Seen**:
A User's record that they have watched a Film, whether entered by hand, synchronised from an external provider, or inferred from a Screening in their Active Schedule that has ended. An inference can be dismissed ("I didn't go").
_Avoid_: Watched, ignored

### Curation

**Organization**:
A body, such as a cinematheque or film club, whose Curators publish Curations and which may operate Venues.
_Avoid_: Org, company, institution

**Membership**:
A User's role within an Organization or a Festival, such as curator.
_Avoid_: Affiliation, staff

**Curator**:
A User holding a curator Membership in an Organization or a Festival.
_Avoid_: Editor, programmer

**Curation**:
A named selection of Programme Entries for a Festival, published by an Organization or by the Festival itself, and authored by Curators.
_Avoid_: List, picks, suggestions

**Curator Note**:
A Curator's comment on a Programme Entry within a Curation.
_Avoid_: Blurb, review

**Suggested Schedule**:
A Schedule generated from a Curation's Programme Entries over a date window. For a signed-in User it is a Draft; for anyone else it is a generic suggestion.
_Avoid_: Suggested programme, curated schedule, recommendation
