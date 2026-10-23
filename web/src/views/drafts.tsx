import { MinusIcon, PlusIcon, TicketIcon } from "@phosphor-icons/react"
import { Link } from "react-router"

import type {
  DiffRowVM,
  DraftBlockVM,
  DraftDayVM,
  DraftListItemVM,
  DraftVM,
  Tick,
} from "@/app/view-models"
import type { Change } from "@/domain/timeline"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

import { ItemLine } from "./items"
import { Page, Place, Spinner } from "./parts"
import { TimeAxis, Track, TrackBlock } from "./track"

const statusWord: Record<DraftVM["status"], string> = {
  solving: "Solving",
  ready: "Ready",
  infeasible: "Nothing fits",
  failed: "Failed",
}

export function DraftListView({ drafts }: { drafts: DraftListItemVM[] }) {
  if (drafts.length === 0) {
    return (
      <Page className="py-16">
        <p className="text-xl">No drafts. Change something, then solve.</p>
      </Page>
    )
  }
  return (
    <Page>
      <h1 className="border-b border-ink py-6 text-xl">Drafts</h1>
      <ol>
        {drafts.map((d) => (
          <li key={d.id} className="border-b border-ink">
            <Link
              to={d.href}
              className="grid grid-cols-[4rem_1fr_auto] items-baseline gap-4 py-4 hover:bg-haze"
            >
              <span>{d.created}</span>
              <span>{d.stale ? "Out of date" : statusWord[d.status]}</span>
              <span className="text-grain">
                {d.changes} {d.changes === 1 ? "change" : "changes"}
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </Page>
  )
}

export function DraftView({ vm }: { vm: DraftVM }) {
  const canAccept = vm.status === "ready" && !vm.stale && !vm.busy
  return (
    <Page>
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-ink py-6">
        <div className="flex items-baseline gap-6">
          {vm.status === "solving" ? (
            <Spinner label="Solving" />
          ) : (
            <h1 className="text-xl">
              {vm.stale ? "Out of date" : statusWord[vm.status]}
            </h1>
          )}
          {vm.scoreDelta && (
            <span aria-label="Score change" className="text-xl text-grain">
              {vm.scoreDelta}
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            className="h-10 px-4 text-base"
            disabled={vm.busy}
            onClick={vm.onDiscard}
          >
            Discard
          </Button>
          {(vm.stale ||
            vm.status === "failed" ||
            vm.status === "infeasible") && (
            <Button
              variant="outline"
              className="h-10 px-4 text-base"
              disabled={vm.busy}
              onClick={vm.onResolve}
            >
              Solve again
            </Button>
          )}
          <Button
            className="h-10 px-5 text-base"
            disabled={!canAccept}
            onClick={vm.onAccept}
          >
            Accept
          </Button>
        </div>
      </header>

      {vm.error && <p className="border-b border-ink py-3">{vm.error}</p>}
      {vm.reasons.map((r) => (
        <p key={r} className="border-b border-ink py-3">
          {r}
        </p>
      ))}
      {/* Informs, never blocks: a freed ticket waits on the Tickets page. */}
      {vm.droppedTickets > 0 && (
        <p className="flex items-center gap-2 border-b border-ink py-3">
          <TicketIcon size={18} weight="light" />
          Frees {vm.droppedTickets}{" "}
          {vm.droppedTickets === 1 ? "ticket" : "tickets"}.
        </p>
      )}

      <div className="grid gap-x-10 md:grid-cols-2">
        <DiffList rows={vm.in} sign="plus" empty="Nothing new." />
        <DiffList rows={vm.out} sign="minus" empty="Nothing out." />
      </div>

      {vm.week && <DraftWeek week={vm.week} ticks={vm.ticks} />}

      {vm.items.length > 0 && (
        <section className="mt-10 max-w-xl">
          <h2 className="border-b border-ink pb-2 text-grain">Changes</h2>
          <ul>
            {vm.items.map((item, i) => (
              <ItemLine key={i} item={item} />
            ))}
          </ul>
        </section>
      )}
    </Page>
  )
}

function DiffList({
  rows,
  sign,
  empty,
}: {
  rows: DiffRowVM[]
  sign: "plus" | "minus"
  empty: string
}) {
  const Glyph = sign === "plus" ? PlusIcon : MinusIcon
  return (
    <ul aria-label={sign === "plus" ? "In" : "Out"}>
      {rows.length === 0 && (
        <li className="border-b border-ink py-4 text-grain">{empty}</li>
      )}
      {rows.map((r) => (
        <li
          key={r.id}
          className="grid grid-cols-[1.5rem_1fr] gap-x-3 border-b border-ink py-4"
        >
          <Glyph
            size={20}
            weight="light"
            className={cn("mt-1", sign === "plus" && "text-stamp")}
          />
          <div>
            <p
              className={cn("title text-2xl", sign === "minus" && "text-grain")}
            >
              {r.title}
            </p>
            <p className="mt-2 flex items-center gap-4 text-grain">
              <span>{r.when}</span>
              <Place venue={r.venue} auditorium={r.auditorium} />
              {r.ticket && (
                <TicketIcon
                  size={16}
                  weight="bold"
                  aria-label="Ticket"
                  className="text-ink"
                />
              )}
            </p>
          </div>
        </li>
      ))}
    </ul>
  )
}

/**
 * Wide screens: the Draft's Schedule as day tracks. In is filled ink, kept
 * steps back, and Out stays as a ghost, the same size, in a lane under its day.
 */
function DraftWeek({ week, ticks }: { week: DraftDayVM[]; ticks: Tick[] }) {
  return (
    <section aria-label="Week" className="mt-10 hidden md:block">
      <TimeAxis ticks={ticks} />
      <ol>
        {week.map((d) => (
          <li
            key={d.key}
            className="grid grid-cols-[5rem_minmax(0,1fr)] border-b border-ink"
          >
            <div
              className={cn(
                "flex flex-col justify-center border-r border-ink py-2",
                !d.changed && "text-grain"
              )}
            >
              <span className="title text-3xl">{d.number}</span>
              <span className="text-xs text-grain">{d.weekday}</span>
            </div>
            <div>
              <Track ticks={ticks}>
                {d.blocks.map((b) => (
                  <DraftBlock key={b.id} block={b} />
                ))}
              </Track>
              {d.ghosts.length > 0 && (
                <Track
                  ticks={ticks}
                  role="group"
                  aria-label="Out"
                  className="border-t border-dotted border-grain/40"
                >
                  {d.ghosts.map((b) => (
                    <DraftBlock key={b.id} block={b} />
                  ))}
                </Track>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}

const tone: Record<Change, string> = {
  kept: "border border-ink/25 bg-screen text-grain hover:bg-haze hover:text-ink",
  in: "border border-ink bg-ink text-screen hover:bg-ink/85",
  out: "border border-dotted border-grain/60 text-grain hover:bg-haze hover:text-ink",
}

function DraftBlock({ block: b }: { block: DraftBlockVM }) {
  const Glyph = b.change === "in" ? PlusIcon : MinusIcon
  return (
    <TrackBlock
      block={b}
      className={cn(
        tone[b.change],
        b.withdrawn && "border-dashed line-through"
      )}
      lead={
        b.change !== "kept" && (
          <>
            <Glyph size="1em" weight="bold" className="shrink-0" />
            <span className="sr-only">{b.word}: </span>
          </>
        )
      }
      ticketLabel={b.change === "out" ? "Frees a ticket" : "Ticket"}
      ticketClassName={cn(
        b.change === "kept" && "text-stamp",
        b.change === "out" && "text-ink"
      )}
    />
  )
}
