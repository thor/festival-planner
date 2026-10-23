// One hook per page. Each reads ports, applies domain rules, and returns a
// view model. Views render it; routes connect the two.

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { useNavigate } from "react-router"

import { recordComparison, removeAt, type ChangeSet } from "@/domain/change-set"
import { describeProblem, problemOf } from "@/domain/errors"
import { dateSpan, festivalsInOrder, phaseOf } from "@/domain/festivals"
import {
  changeWord,
  describeItem,
  lookupOf,
  signed,
  when,
  type Lookup,
} from "@/domain/labels"
import type {
  DayKey,
  Draft,
  DraftId,
  Festival,
  ProgrammeEntryId,
  Screening,
} from "@/domain/model"
import { clock, dayKey, dayNumber, festivalDays, weekday } from "@/domain/time"
import {
  fitSpan,
  hourTicks,
  layDays,
  layDiff,
  nowOn,
  type Placed,
} from "@/domain/timeline"

import { usePendingChangeSet } from "./change-set-store"
import { useNow } from "./now"
import { usePorts } from "./ports"
import {
  keys,
  useDraft,
  useFestival,
  useFestivals,
  usePlanning,
  useProgramme,
} from "./queries"
import { entryHref, metaOf, useEntryModels } from "./screenings"
import { useSignedIn } from "./session"
import { useTicketModels } from "./tickets"
import type {
  CompareVM,
  DiffRowVM,
  DraftListItemVM,
  DraftVM,
  FestivalVM,
  FilmVM,
  ItemVM,
  Load,
  ProgrammeVM,
  ScreeningVM,
  TicketsVM,
  TrayVM,
  ScheduleVM,
} from "./view-models"

const loading = { state: "loading" } as const
const missing = (message: string) => ({ state: "missing", message }) as const
const ready = <T>(value: T) => ({ state: "ready", value }) as const

function useFestivalData(slug: string) {
  const festival = useFestival(slug)
  const programme = useProgramme(festival.data)
  const planning = usePlanning(festival.data)
  return { festival, programme, planning }
}

export function useHomePage(): Load<FestivalVM[]> {
  const festivals = useFestivals()
  if (festivals.isPending) return loading
  if (festivals.isError) return missing("Server unreachable.")
  if (!festivals.data.length) return missing("No festivals yet.")
  return ready(
    festivalsInOrder(festivals.data).map((f) => ({
      slug: f.slug,
      name: f.name,
      href: `/${f.slug}`,
      dates: dateSpan(f),
      phase: phaseOf(f),
    }))
  )
}

export function useFrame(slug: string) {
  const { festival, programme, planning } = useFestivalData(slug)
  const tickets = useTicketModels(festival.data, planning.data, programme.data)
  return {
    festival: festival.data?.name ?? "",
    slug,
    letGo: tickets.letGo.length,
  }
}

export function useTicketsPage(slug: string): Load<TicketsVM> {
  const { festival, programme, planning } = useFestivalData(slug)
  const tickets = useTicketModels(festival.data, planning.data, programme.data)
  if (festival.isPending || planning.isPending || programme.isPending)
    return loading
  if (!festival.data) return missing("No such festival.")
  if (!planning.data) return missing("Sign in to see tickets.")
  return ready({
    letGo: tickets.letGo,
    held: tickets.held,
    programmeHref: `/${festival.data.slug}`,
  })
}

export function useProgrammePage(
  slug: string,
  day: string | null
): Load<ProgrammeVM> {
  const { festival, programme, planning } = useFestivalData(slug)
  const models = useEntryModels(festival.data, planning.data)
  if (festival.isPending || programme.isPending) return loading
  if (!festival.data) return missing("No such festival.")
  const f = festival.data
  const onDay = (s: Screening) =>
    !day || dayKey(s.startTime, f.timeZone) === day
  const entries = (programme.data ?? [])
    .filter((e) => e.screenings.some(onDay))
    .map((e) => models.entry(e, onDay))
  return ready({
    festival: f.name,
    allHref: `/${f.slug}`,
    allCurrent: !day,
    days: festivalDays(f).map((d) => ({
      key: d,
      number: dayNumber(d),
      weekday: weekday(d),
      href: `/${f.slug}?day=${d}`,
      current: d === day,
    })),
    entries,
  })
}

export function useFilmPage(slug: string, entryId: string): Load<FilmVM> {
  const { festival, programme, planning } = useFestivalData(slug)
  const models = useEntryModels(festival.data, planning.data)
  if (festival.isPending || programme.isPending) return loading
  const entry = programme.data?.find((e) => e.id === entryId)
  if (!festival.data || !entry) return missing("No such film.")
  const vm = models.entry(entry)
  const selected = selectedViewing(vm.screenings)
  return ready({
    title: entry.title,
    buy:
      !vm.screenings.some((s) => s.ticket) && selected?.buyHref
        ? selected
        : null,
    meta: metaOf(entry),
    url: entry.url,
    entry: vm,
    backHref: `/${festival.data.slug}`,
  })
}

/** The viewing in the Active Schedule, else the committed one. */
function selectedViewing(screenings: ScreeningVM[]) {
  return (
    screenings.find((s) => s.scheduled && !s.marks.excluded) ??
    screenings.find((s) => s.marks.committed)
  )
}

export function useSchedulePage(
  slug: string
): Load<ScheduleVM> & { signedIn: boolean } {
  const { festival, programme, planning } = useFestivalData(slug)
  const signedIn = useSignedIn()
  const now = useNow()
  const ticketModels = useTicketModels(
    festival.data,
    planning.data,
    programme.data
  )
  if (festival.isPending || (signedIn && planning.isPending))
    return { ...loading, signedIn }
  if (!festival.data) return { ...missing("No such festival."), signedIn }
  const f = festival.data
  const p = planning.data
  const schedule = p?.activeSchedule
  const screenings = schedule?.screenings ?? []
  const span = fitSpan(f, screenings)
  const today = dayKey(now, f.timeZone)
  const mark = nowOn(f, span, now)
  const tickets = new Set(p?.tickets.map((t) => t.screening.id))
  const committed = new Set(p?.inputs.screeningCommitments)
  const films = new Set(p?.inputs.filmCommitments)
  return {
    signedIn,
    ...ready({
      number: schedule?.number ?? null,
      count: screenings.length,
      programmeHref: `/${f.slug}`,
      ticks: hourTicks(span),
      letGo: ticketModels.letGo.length,
      ticketsHref: `/${f.slug}/tickets`,
      problems: ticketModels.problems,
      days: layDays(f, screenings, span).map((row) => ({
        ...dayOf(row.day, today, mark),
        blocks: row.placed.map((placed) => ({
          ...blockOf(f, placed),
          ticket: tickets.has(placed.screening.id),
          committed:
            committed.has(placed.screening.id) ||
            films.has(placed.screening.programmeEntryId),
        })),
      })),
    }),
  }
}

/**
 * A Festival Day's heading on its track, and now on it. Just after midnight
 * now is on the evening before, while today has moved on.
 */
function dayOf(day: DayKey, today: DayKey, mark: ReturnType<typeof nowOn>) {
  return {
    key: day,
    number: dayNumber(day),
    weekday: weekday(day),
    today: day === today,
    now: mark?.day === day ? mark.left : null,
  }
}

/** A Screening as a block on its day track. */
function blockOf(f: Festival, { screening: s, left, width }: Placed) {
  return {
    id: s.id,
    title: s.title,
    time: clock(s.startTime, f.timeZone),
    end: clock(s.endTime, f.timeZone),
    venue: s.venue.name,
    auditorium: s.auditorium,
    href: entryHref(f, { id: s.programmeEntryId }),
    left,
    width,
    withdrawn: s.withdrawn,
  }
}

function itemsOf(
  set: ChangeSet,
  lookup: Lookup,
  onRemove?: (index: number) => void
): ItemVM[] {
  return set.map((item, i) => ({
    ...describeItem(item, lookup),
    onRemove: onRemove && (() => onRemove(i)),
  }))
}

function useLookup(festival: Festival | null | undefined) {
  const programme = useProgramme(festival)
  return lookupOf(programme.data ?? [], festival?.timeZone ?? "UTC")
}

export function useTray(slug: string): TrayVM {
  const { planning: port } = usePorts()
  const client = useQueryClient()
  const navigate = useNavigate()
  const festival = useFestival(slug)
  const lookup = useLookup(festival.data)
  const signedIn = useSignedIn()
  const [set, update] = usePendingChangeSet(festival.data?.id)
  const solve = useMutation({
    mutationFn: () => port.createDraft(festival.data!.id, set),
    onSuccess: (draft) => {
      update(() => [])
      // Show it at once, then fetch its diff: createDraft does not return one.
      client.setQueryData(keys.draft(draft.id), draft)
      void client.invalidateQueries({ queryKey: keys.draft(draft.id) })
      void client.invalidateQueries({
        queryKey: keys.planning(draft.festivalId),
      })
      void navigate(`/${slug}/drafts/${encodeURIComponent(draft.id)}`)
    },
  })
  return {
    items: itemsOf(set, lookup, (i) => update((cs) => removeAt(i, cs))),
    signedIn,
    busy: solve.isPending,
    error: solve.error ? describeProblem(problemOf(solve.error)) : null,
    onSolve: () => solve.mutate(),
    onClear: () => update(() => []),
  }
}

const statuses: Record<Draft["status"], DraftVM["status"]> = {
  SOLVING: "solving",
  READY: "ready",
  INFEASIBLE: "infeasible",
  FAILED: "failed",
}
const statusOf = (d: Draft) => statuses[d.status]

export function useDraftsPage(slug: string): Load<DraftListItemVM[]> {
  const { festival, planning } = useFestivalData(slug)
  if (festival.isPending || planning.isPending) return loading
  if (!festival.data) return missing("No such festival.")
  if (!planning.data) return missing("Sign in to see drafts.")
  const tz = festival.data.timeZone
  return ready(
    [...planning.data.drafts].reverse().map((d) => ({
      id: d.id,
      href: `/${slug}/drafts/${encodeURIComponent(d.id)}`,
      status: statusOf(d),
      stale: d.stale,
      changes: d.changeSet.length,
      created: clock(d.createdAt, tz),
    }))
  )
}

export function useDraftPage(slug: string, draftId: string): Load<DraftVM> {
  const { planning: port } = usePorts()
  const client = useQueryClient()
  const navigate = useNavigate()
  const festival = useFestival(slug)
  const lookup = useLookup(festival.data)
  const id = draftId as DraftId
  const draft = useDraft(id)
  const planning = usePlanning(festival.data)
  const now = useNow()

  const settle = () => client.invalidateQueries({ queryKey: ["planning"] })
  const accept = useMutation({
    mutationFn: () => port.acceptDraft(id),
    onSuccess: () => {
      void settle()
      void navigate(`/${slug}/schedule`)
    },
  })
  const discard = useMutation({
    mutationFn: () => port.discardDraft(id),
    onSuccess: () => {
      void settle()
      void navigate(`/${slug}/drafts`)
    },
  })
  const resolve = useMutation({
    mutationFn: () => port.resolveDraft(id),
    onSuccess: (d) => {
      client.setQueryData(keys.draft(id), d)
      void settle()
    },
  })

  if (draft.isPending || !festival.data) return loading
  if (!draft.data) return missing("Draft gone.")
  const d = draft.data
  const f = festival.data
  const tz = f.timeZone
  // Freed tickets, and every ticket held, on any block or row.
  const held = new Set([
    ...(d.diff?.droppedTickets.map((s) => s.id) ?? []),
    ...(planning.data?.tickets.map((t) => t.screening.id) ?? []),
  ])
  const span = fitSpan(f, [...d.screenings, ...(d.diff?.removed ?? [])])
  const today = dayKey(now, tz)
  const mark = nowOn(f, span, now)
  const week =
    d.diff &&
    layDiff(f, d.screenings, d.diff, span).map((row) => {
      const blocks = row.placed.map(({ change, ...placed }) => ({
        ...blockOf(f, placed),
        ticket: held.has(placed.screening.id),
        change,
        word: change === "kept" ? null : changeWord[change],
      }))
      return {
        ...dayOf(row.day, today, mark),
        changed: row.changed,
        blocks: blocks.filter((b) => b.change !== "out"),
        ghosts: blocks.filter((b) => b.change === "out"),
      }
    })
  const row = (s: Screening): DiffRowVM => ({
    id: s.id,
    title: s.title,
    when: when(s, tz),
    venue: s.venue.name,
    auditorium: s.auditorium,
    ticket: held.has(s.id),
  })
  const failed = accept.error ?? discard.error ?? resolve.error
  return ready({
    status: statusOf(d),
    stale: d.stale,
    scoreDelta:
      d.diff && Math.abs(d.diff.scoreDelta) >= 0.05
        ? signed(d.diff.scoreDelta)
        : null,
    in: d.diff?.added.map(row) ?? [],
    out: d.diff?.removed.map(row) ?? [],
    droppedTickets: d.diff?.droppedTickets.length ?? 0,
    week,
    ticks: hourTicks(span),
    reasons: d.reasons,
    items: itemsOf(d.changeSet, lookup),
    busy: accept.isPending || discard.isPending || resolve.isPending,
    error: failed ? describeProblem(problemOf(failed)) : null,
    onAccept: () => accept.mutate(),
    onDiscard: () => discard.mutate(),
    onResolve: () => resolve.mutate(),
  })
}

export function useComparePage(slug: string): Load<CompareVM> {
  const { festival, planning } = useFestivalData(slug)
  const [set, update] = usePendingChangeSet(festival.data?.id)
  const [skipped, setSkipped] = useState<string[]>([])
  const [picked, setPicked] = useState<"a" | "b" | null>(null)
  if (festival.isPending || planning.isPending) return loading
  if (!planning.data) return missing("Sign in to compare.")

  const key = (a: string, b: string) => [a, b].sort().join("|")
  const done = new Set([
    ...skipped,
    ...set.flatMap((i) =>
      i.kind === "recordComparison" ? [key(i.preferredId, i.otherId)] : []
    ),
  ])
  const open = planning.data.suggestions.filter(
    (p) => !done.has(key(p.scheduled.id, p.other.id))
  )
  const pair = open[0]
  const pick =
    (side: "a" | "b", preferred: ProgrammeEntryId, other: ProgrammeEntryId) =>
    () => {
      setPicked(side)
      // Let the loser fade before the next pair.
      setTimeout(() => {
        update((cs) => recordComparison(preferred, other, cs))
        setPicked(null)
      }, 420)
    }
  return ready({
    picked,
    left: open.length,
    onSkip: () =>
      pair && setSkipped((s) => [...s, key(pair.scheduled.id, pair.other.id)]),
    pair: pair
      ? {
          a: {
            title: pair.scheduled.title,
            meta: metaOf(pair.scheduled),
            onPick: pick("a", pair.scheduled.id, pair.other.id),
          },
          b: {
            title: pair.other.title,
            meta: metaOf(pair.other),
            onPick: pick("b", pair.other.id, pair.scheduled.id),
          },
        }
      : null,
  })
}
