import { TicketIcon, WarningIcon } from "@phosphor-icons/react"
import { Link } from "react-router"

import type { ScheduleVM } from "@/app/view-models"
import { cn } from "@/lib/utils"

import { Button } from "@/components/ui/button"

import { Page, Place } from "./parts"
import { TimeAxis, Track, TrackBlock } from "./track"

export function ScheduleView({ vm }: { vm: ScheduleVM }) {
  if (vm.number === null) {
    return (
      <Page className="py-16">
        <p className="text-xl">No schedule yet.</p>
        <Link
          to={vm.programmeHref}
          className="mt-4 inline-block underline underline-offset-4"
        >
          Pick films
        </Link>
      </Page>
    )
  }
  return (
    <Page>
      <header className="flex items-baseline justify-between border-b border-ink py-6">
        <h1 className="text-xl">Schedule {vm.number}</h1>
        <p className="text-grain">{vm.count} films</p>
      </header>

      <Notices vm={vm} />

      <TimeAxis ticks={vm.ticks} />

      <ol>
        {vm.days.map((d) => (
          <li
            key={d.key}
            className="grid grid-cols-[3.75rem_minmax(0,1fr)] border-b border-ink md:grid-cols-[5rem_minmax(0,1fr)]"
          >
            {/* Narrow: pinned under the bar while its day scrolls by. */}
            <div className="border-r border-ink md:flex md:flex-col md:justify-center">
              <div className="sticky top-10 flex flex-col py-2 md:static">
                <span className="title text-2xl md:text-3xl">{d.number}</span>
                <span className="text-xs text-grain">{d.weekday}</span>
              </div>
            </div>

            {/* Wide: a track from 10 to 01. */}
            <Track ticks={vm.ticks} className="hidden md:block">
              {d.blocks.map((b) => (
                <TrackBlock
                  key={b.id}
                  block={b}
                  className={cn(
                    "border border-ink bg-screen hover:bg-haze",
                    b.committed && "border-2 border-stamp",
                    b.ticket &&
                      "border-stamp bg-stamp text-stamp-ink hover:bg-stamp/85",
                    b.withdrawn && "border-dashed text-grain line-through"
                  )}
                />
              ))}
            </Track>

            {/* Narrow: a list. */}
            <ul className="md:hidden">
              {d.blocks.length === 0 && (
                <li className="px-3 py-3 text-grain">Free</li>
              )}
              {d.blocks.map((b) => (
                <li key={b.id} className="border-b border-haze last:border-b-0">
                  {/* Start and title, then end and place. */}
                  <Link
                    to={b.href}
                    className={cn(
                      "grid grid-cols-[auto_minmax(0,1fr)_auto] items-baseline gap-x-3 px-3 py-2",
                      b.committed && "shadow-[inset_2px_0_var(--color-stamp)]",
                      b.ticket && "text-stamp",
                      b.withdrawn && "text-grain line-through"
                    )}
                  >
                    <span className="text-right">{b.time}</span>
                    <span className="swipe">{b.title}</span>
                    {b.ticket && (
                      <TicketIcon
                        size={16}
                        weight="bold"
                        aria-label="Ticket"
                        className="col-start-3 row-span-2 row-start-1 self-center"
                      />
                    )}
                    <span className="col-start-1 text-right text-sm text-grain">
                      {b.end}
                    </span>
                    <Place
                      venue={b.venue}
                      auditorium={b.auditorium}
                      className="truncate text-sm text-grain"
                    />
                  </Link>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ol>
    </Page>
  )
}

/** One quiet line per thing to do; details live on the Tickets page. */
function Notices({ vm }: { vm: ScheduleVM }) {
  if (vm.letGo === 0 && vm.problems.length === 0) return null
  return (
    <ul className="border-b border-ink">
      {vm.letGo > 0 && (
        <li className="border-b border-haze last:border-b-0">
          <Link
            to={vm.ticketsHref}
            className="flex items-center gap-3 py-3 text-stamp hover:underline hover:underline-offset-4"
          >
            <TicketIcon size={18} weight="light" className="shrink-0" />
            {vm.letGo} {vm.letGo === 1 ? "ticket" : "tickets"} to let go
          </Link>
        </li>
      )}
      {vm.problems.map((p) => (
        <li
          key={p.id}
          className="flex items-center justify-between gap-4 border-b border-haze py-2 last:border-b-0"
        >
          <span className="flex min-w-0 items-center gap-3">
            <WarningIcon size={18} weight="light" className="shrink-0" />
            <span className="truncate">{p.title} withdrawn.</span>
          </span>
          <Button
            variant="outline"
            aria-pressed={p.on}
            onClick={p.onAct}
            className={cn(
              "h-9 shrink-0 border-ink px-3 text-base",
              p.on && "border-stamp bg-stamp text-stamp-ink hover:bg-stamp/85"
            )}
          >
            {p.action}
          </Button>
        </li>
      ))}
    </ul>
  )
}
