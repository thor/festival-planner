# Drafts are change sets, not just solver output

A Draft holds a change set (e.g. add a Screening Commitment, release a commitment, change a Preference, adopt a Curation) together with the Schedule solved from applying it. A User's commitments and Preferences only change when a Draft is accepted, which applies the change set and makes its Schedule Active atomically. We chose this over editing commitments and Preferences directly, with Drafts as mere solver output, because users need to compare several "what if" Drafts side by side; Drafts solved against an older Active Schedule become Stale and can be re-solved.

## Consequences

Solving deliberately has no stability bonus towards the current Active Schedule: if a change reshuffles uncommitted Screenings for a better result, that is accepted, and heavy reshuffling is treated as a signal that the User has expressed too few preferences rather than something to suppress.
