// Shared wiring: marks and toggles for Screenings and Programme Entries.

import { useMutation, useQueryClient } from "@tanstack/react-query"

import {
  emptyInputs,
  entryMarks,
  screeningMarks,
  toggleFilmCommitment,
  toggleFilmExclusion,
  toggleScreeningCommitment,
  toggleScreeningExclusion,
} from "@/domain/change-set"
import { when } from "@/domain/labels"
import type { Festival, Planning, ProgrammeEntry, Screening, ScreeningId } from "@/domain/model"
import { clock, dayKey, isPast, shortDay } from "@/domain/time"

import { usePendingChangeSet } from "./change-set-store"
import { usePorts } from "./ports"
import { keys } from "./queries"
import type { EntryVM, ScreeningVM } from "./view-models"

export function entryHref(festival: Festival, entry: { id: string }) {
  return `/${festival.slug}/film/${encodeURIComponent(entry.id)}`
}

export function metaOf(entry: ProgrammeEntry): string[] {
  return [entry.year ? String(entry.year) : null, entry.country].filter((x): x is string => !!x)
}

export { when }

/** Builds Screening and Programme Entry view models with their actions. */
export function useEntryModels(festival: Festival | null | undefined, planning: Planning | null | undefined) {
  const { planning: port } = usePorts()
  const client = useQueryClient()
  const [set, update] = usePendingChangeSet(festival?.id)
  const inputs = planning?.inputs ?? emptyInputs
  const signedIn = !!planning
  const scheduled = new Set(planning?.activeSchedule?.screenings.map((s) => s.id))
  const tickets = new Set(planning?.tickets.map((t) => t.screening.id))

  const ticket = useMutation({
    mutationFn: ({ id, has }: { id: ScreeningId; has: boolean }) =>
      has ? port.removeTicket(id) : port.recordTicket(id),
    onSettled: () => festival && client.invalidateQueries({ queryKey: keys.planning(festival.id) }),
  })

  const screening = (s: Screening): ScreeningVM => {
    const tz = festival!.timeZone
    const open = signedIn && !s.withdrawn && !isPast(s.startTime)
    const has = tickets.has(s.id)
    return {
      id: s.id,
      day: shortDay(dayKey(s.startTime, tz)),
      time: clock(s.startTime, tz),
      venue: s.venue.name,
      withdrawn: s.withdrawn,
      past: isPast(s.startTime),
      scheduled: scheduled.has(s.id),
      ticket: has,
      buyHref: open && !has && s.ticketUrl ? s.ticketUrl : null,
      event: s.events[0]?.description ?? null,
      marks: screeningMarks(s.id, inputs, set),
      onCommit: open ? () => update((cs) => toggleScreeningCommitment(s.id, inputs, cs)) : undefined,
      onExclude: open ? () => update((cs) => toggleScreeningExclusion(s.id, inputs, cs)) : undefined,
      onTicket: signedIn && !s.withdrawn ? () => ticket.mutate({ id: s.id, has }) : undefined,
    }
  }

  const entry = (e: ProgrammeEntry, only?: (s: Screening) => boolean): EntryVM => ({
    id: e.id,
    title: e.title,
    href: entryHref(festival!, e),
    meta: metaOf(e),
    marks: entryMarks(e.id, inputs, set),
    screenings: e.screenings.filter(only ?? (() => true)).map(screening),
    onCommit: signedIn ? () => update((cs) => toggleFilmCommitment(e.id, inputs, cs)) : undefined,
    onExclude: signedIn ? () => update((cs) => toggleFilmExclusion(e.id, inputs, cs)) : undefined,
  })

  return { entry, screening, signedIn }
}
