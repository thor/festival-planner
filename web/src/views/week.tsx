import { TicketIcon, WarningIcon } from "@phosphor-icons/react"
import { Link } from "react-router"

import type { WeekVM } from "@/app/view-models"
import { cn } from "@/lib/utils"

import { Button } from "@/components/ui/button"

import { Page } from "./parts"

export function WeekView({ vm }: { vm: WeekVM }) {
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

      <div
        aria-hidden
        className="relative ml-20 hidden h-8 border-b border-ink md:block"
      >
        {vm.ticks.map((t) => (
          <span
            key={t.label}
            className="absolute bottom-1 -translate-x-1/2 text-xs text-grain"
            style={{ left: `${t.left * 100}%` }}
          >
            {t.label}
          </span>
        ))}
      </div>

      <ol>
        {vm.days.map((d) => (
          <li
            key={d.key}
            className="grid grid-cols-[5rem_minmax(0,1fr)] border-b border-ink"
          >
            <div className="flex flex-col justify-center border-r border-ink py-2">
              <span className="title text-3xl">{d.number}</span>
              <span className="text-xs text-grain">{d.weekday}</span>
            </div>

            {/* Wide: a track from 10 to 01. */}
            <div className="relative hidden h-24 md:block">
              {vm.ticks.map((t) => (
                <span
                  key={t.label}
                  aria-hidden
                  className="absolute inset-y-0 border-l border-haze"
                  style={{ left: `${t.left * 100}%` }}
                />
              ))}
              {d.blocks.map((b) => (
                <Link
                  key={b.id}
                  to={b.href}
                  className={cn(
                    "absolute inset-y-2 flex flex-col justify-between overflow-hidden border border-ink bg-screen px-2 py-1 hover:bg-haze",
                    b.committed && "border-2 border-stamp",
                    b.ticket &&
                      "border-stamp bg-stamp text-stamp-ink hover:bg-stamp/85",
                    b.withdrawn && "border-dashed text-grain line-through"
                  )}
                  style={{
                    left: `${b.left * 100}%`,
                    width: `${b.width * 100}%`,
                  }}
                >
                  <span className="truncate text-sm leading-tight font-medium">
                    {b.title}
                  </span>
                  <span className="flex items-center gap-1 truncate text-xs">
                    {b.ticket && (
                      <TicketIcon size={14} weight="bold" aria-label="Ticket" />
                    )}
                    {b.time} {b.venue}
                  </span>
                </Link>
              ))}
            </div>

            {/* Narrow: a list. */}
            <ul className="md:hidden">
              {d.blocks.length === 0 && (
                <li className="px-3 py-3 text-grain">Free</li>
              )}
              {d.blocks.map((b) => (
                <li key={b.id} className="border-b border-haze last:border-b-0">
                  <Link
                    to={b.href}
                    className={cn(
                      "flex items-baseline gap-3 px-3 py-2",
                      b.ticket && "text-stamp",
                      b.withdrawn && "text-grain line-through"
                    )}
                  >
                    <span className="w-12 shrink-0 text-right">{b.time}</span>
                    <span className="swipe min-w-0 flex-1">{b.title}</span>
                    {b.ticket && (
                      <TicketIcon size={16} weight="bold" aria-label="Ticket" />
                    )}
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
function Notices({ vm }: { vm: WeekVM }) {
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
