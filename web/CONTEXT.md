# Web

The words a User reads and acts on in the web app. Every term here maps onto
the planning language in [GLOSSARY.md](../GLOSSARY.md); where the screen needs
a shorter or friendlier word, this file says which concept it stands for.

## Language

### Pages

**Home**:
The first page: the app's name, one line on what it does, and every Festival, on now first, then those ahead, then those over. The app icon in the header leads back to it.
_Avoid_: Landing, index, festival picker

**Programme**:
The page listing a Festival's Programme Entries and their Screenings, one Festival Day at a time or all at once.
_Avoid_: Catalogue, listing, lineup

**Film page**:
The page for one Programme Entry and its Screenings. "Film" here always means the Programme Entry, as in Film Commitment, never the festival-independent Film.
_Avoid_: Entry page, title page

**Schedule page**:
The page showing the Active Schedule as one row per Festival Day.
_Avoid_: Week, calendar, itinerary

**Tickets page**:
The page listing the User's Tickets for a Festival: Tickets to let go above Held Tickets.
_Avoid_: Wallet, bookings, purchases

### Time

**Festival Day**:
A calendar day in the Festival's time zone, from its start date to its end date. A Screening belongs to the Festival Day it starts on, even if it ends after midnight.
_Avoid_: Date (when meaning a festival day), local day

### Changing the Schedule

**Pending Change Set**:
The Change Set a User is assembling for one Festival before it becomes a Draft. It is not saved anywhere and has no effect until solved.
_Avoid_: Cart, basket, unsaved changes

**Tray**:
Where the Pending Change Set is shown, counted and solved.
_Avoid_: Drawer, staging area

**Commit**:
To add a Screening Commitment, or a Film Commitment on the Film page, to the Pending Change Set. Its opposite is **Release**.
_Avoid_: Pin, book, add to schedule

**Exclude**:
To add an Excluded Screening or Programme Entry to the Pending Change Set. Its opposite is **Include**.
_Avoid_: Hide, ignore, skip

**Solve**:
To turn the Pending Change Set into a Draft. **Solve again** re-solves an existing Draft against the current Active Schedule.
_Avoid_: Optimise, run, generate

**Repair**:
To make a Draft with an empty Change Set, so the Active Schedule's own inputs are solved again after a Screening in it is Withdrawn.
_Avoid_: Solve again (that re-solves a Draft), fix, refresh

**In** and **Out**:
The Screenings a Draft brings into the Schedule and takes out of it. An Out Screening was only not chosen; a Withdrawn one is a different thing.
_Avoid_: Added, removed, dropped

**Accept**:
To make a Draft's Schedule the Active Schedule. It never changes Tickets.
_Avoid_: Apply, confirm, save

**Score change**:
How much better or worse a Draft scores than the Active Schedule under the Draft's Preferences.
_Avoid_: Delta, gain

### Tickets

**Ticket to let go**:
A Ticket the User should get rid of because its Screening is Withdrawn, or because it is upcoming and not in the Active Schedule. It stays one until the User keeps it or says it is gone; nothing lets go of it automatically.
_Avoid_: Loose ticket, orphan ticket, unscheduled ticket, dropped ticket

**Held Ticket**:
A Ticket that is not a Ticket to let go: its Screening is in the Active Schedule, or has already started.
_Avoid_: Active ticket, valid ticket

**Keep**:
A Commit to a Ticket's Screening, named for the Ticket. It is not an operation of its own: it adds a Screening Commitment to the Pending Change Set, like Commit.
_Avoid_: Restore, reschedule

**Gone**:
The User's statement that they no longer hold a Ticket (sold, refunded, exchanged or given away). It removes the Ticket.
_Avoid_: Delete, cancel, drop

**Freed Ticket**:
A Ticket whose Screening is Out in a Draft. Accepting the Draft makes it a Ticket to let go; it does not remove it.
_Avoid_: Dropped ticket, lost ticket

### Attention

**Schedule Problem**:
A Flag about the Active Schedule itself: a Withdrawn Screening in it, or a Withdrawn commitment. Flags about Tickets are shown as Tickets to let go instead.
_Avoid_: Warning, error, alert

### Comparing

**Compare**:
To record a Comparison by choosing, from a Comparison Suggestion's pair, the Programme Entry the User would rather see. Skipping records nothing.
_Avoid_: Prefer, vote, rank, swipe
