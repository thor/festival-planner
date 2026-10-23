// Tickets and Schedule problems as view models, shared by the Tickets page,
// the Schedule page's notice line and the nav count.

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router"

import {
  emptyInputs,
  entryMarks,
  screeningMarks,
  toggleFilmCommitment,
  toggleScreeningCommitment,
} from "@/domain/change-set"
import { letGoWord, when } from "@/domain/labels"
import type {
  Festival,
  Planning,
  ProgrammeEntry,
  ProgrammeEntryId,
  ScreeningId,
  Ticket,
} from "@/domain/model"
import {
  festivalTickets,
  scheduleProblems,
  sortTickets,
} from "@/domain/tickets"

import { usePendingChangeSet } from "./change-set-store"
import { usePorts } from "./ports"
import { keys } from "./queries"
import { entryHref } from "./screenings"
import type { ProblemVM, TicketVM } from "./view-models"

export function useTicketModels(
  festival: Festival | null | undefined,
  planning: Planning | null | undefined,
  programme: ProgrammeEntry[] | undefined
) {
  const { planning: port } = usePorts()
  const client = useQueryClient()
  const navigate = useNavigate()
  const [set, update] = usePendingChangeSet(festival?.id)
  const inputs = planning?.inputs ?? emptyInputs
  const settle = () =>
    festival &&
    client.invalidateQueries({ queryKey: keys.planning(festival.id) })

  const gone = useMutation({
    mutationFn: (id: ScreeningId) => port.removeTicket(id),
    onSettled: settle,
  })
  const solve = useMutation({
    mutationFn: () => port.createDraft(festival!.id, []),
    onSuccess: (draft) => {
      void settle()
      void navigate(`/${festival!.slug}/drafts/${encodeURIComponent(draft.id)}`)
    },
  })

  if (!festival || !planning) return { letGo: [], held: [], problems: [] }
  const tz = festival.timeZone
  const scheduled = new Set(
    planning.activeSchedule?.screenings.map((s) => s.id)
  )
  const mine = festivalTickets(
    planning.tickets,
    programme ?? [],
    planning.flags
  )
  const sorted = sortTickets(mine, scheduled)

  const row = (t: Ticket, notes: string[]): TicketVM => {
    const s = t.screening
    return {
      id: s.id,
      title: s.title,
      href: entryHref(festival, { id: s.programmeEntryId }),
      when: when(s, tz),
      venue: s.venue.name,
      notes: [
        ...notes,
        t.refundable ? "Refundable" : null,
        t.exchangeable ? "Exchangeable" : null,
      ].filter((x): x is string => !!x),
    }
  }

  const elsewhere = (s: Ticket["screening"]) =>
    planning.activeSchedule?.screenings.find(
      (x) => x.programmeEntryId === s.programmeEntryId && x.id !== s.id
    )

  const letGo: TicketVM[] = sorted.letGo.map(({ ticket, reason }) => {
    const s = ticket.screening
    // Same film, other time: say when, so Keep reads as a swap.
    const other = reason === "notScheduled" ? elsewhere(s) : undefined
    return {
      ...row(ticket, [
        other ? `Seeing it ${when(other, tz)}` : letGoWord[reason],
      ]),
      keeping: screeningMarks(s.id, inputs, set).committed,
      onKeep:
        reason === "notScheduled"
          ? () => update((cs) => toggleScreeningCommitment(s.id, inputs, cs))
          : undefined,
      festivalHref: reason === "withdrawn" ? s.ticketUrl : null,
      onGone: gone.isPending ? undefined : () => gone.mutate(s.id),
    }
  })

  const problems: ProblemVM[] = scheduleProblems(planning.flags).flatMap(
    (f): ProblemVM[] => {
      if (f.kind === "WITHDRAWN_IN_SCHEDULE" && f.screening) {
        return [
          {
            id: f.screening.id,
            title: f.screening.title,
            action: "Solve again",
            on: false,
            onAct: () => solve.mutate(),
          },
        ]
      }
      if (f.screening) {
        const id = f.screening.id
        return [
          {
            id,
            title: f.screening.title,
            action: "Release",
            on: !screeningMarks(id, inputs, set).committed,
            onAct: () =>
              update((cs) => toggleScreeningCommitment(id, inputs, cs)),
          },
        ]
      }
      const entryId = f.programmeEntryId as ProgrammeEntryId | null
      if (!entryId) return []
      return [
        {
          id: entryId,
          title: programme?.find((e) => e.id === entryId)?.title ?? "A film",
          action: "Release",
          on: !entryMarks(entryId, inputs, set).committed,
          onAct: () =>
            update((cs) => toggleFilmCommitment(entryId, inputs, cs)),
        },
      ]
    }
  )

  // Committed and scheduled gives two Flags for one Screening. Keep the first:
  // the backend lists commitments first, and Release is what unblocks a solve.
  const seen = new Set<string>()
  const unique = problems.filter((p) => !seen.has(p.id) && !!seen.add(p.id))

  return { letGo, held: sorted.held.map((t) => row(t, [])), problems: unique }
}
