// Tickets a User holds, sorted into the ones to let go and the ones to keep.
// Letting go is its own flow: accepting a Schedule never drops a Ticket, so
// a Ticket stays here until the User says it is gone.

import type { Flag, ProgrammeEntry, ScreeningId, Ticket } from "./model"
import { isPast } from "./time"

export type LetGoReason = "withdrawn" | "notScheduled"

export interface LetGo {
  ticket: Ticket
  reason: LetGoReason
}

export interface SortedTickets {
  letGo: LetGo[]
  held: Ticket[]
}

/**
 * The Tickets for one Festival. A Screening has no Festival of its own, so a
 * Ticket belongs if its Screening is in the programme or a Flag names it
 * (Withdrawn Screenings are only reachable that way).
 */
export function festivalTickets(tickets: Ticket[], programme: ProgrammeEntry[], flags: Flag[]): Ticket[] {
  const ids = new Set<string>(programme.flatMap((e) => e.screenings.map((s) => s.id)))
  for (const f of flags) if (f.screening) ids.add(f.screening.id)
  return tickets.filter((t) => ids.has(t.screening.id))
}

/** Same rules as the backend's Flags; a past, unscheduled Ticket is just held. */
export function sortTickets(tickets: Ticket[], scheduled: ReadonlySet<ScreeningId>, now = new Date()): SortedTickets {
  const byTime = [...tickets].sort((a, b) => a.screening.startTime.localeCompare(b.screening.startTime))
  const letGo: LetGo[] = []
  const held: Ticket[] = []
  for (const ticket of byTime) {
    const s = ticket.screening
    if (s.withdrawn) letGo.push({ ticket, reason: "withdrawn" })
    else if (!scheduled.has(s.id) && !isPast(s.startTime, now)) letGo.push({ ticket, reason: "notScheduled" })
    else held.push(ticket)
  }
  return { letGo, held }
}

/** Flags about the Schedule itself; ticket Flags live with the Tickets. */
export function scheduleProblems(flags: Flag[]): Flag[] {
  return flags.filter((f) => f.kind === "WITHDRAWN_IN_SCHEDULE" || f.kind === "WITHDRAWN_COMMITMENT")
}
