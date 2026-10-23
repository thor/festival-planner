// The day track shared by the Schedule and a Draft: hours across, fitted to
// the Screenings shown.

import { TicketIcon } from "@phosphor-icons/react"
import type { ComponentProps, ReactNode } from "react"
import { Link } from "react-router"

import type { Tick, TrackBlockVM } from "@/app/view-models"
import { cn } from "@/lib/utils"

import { Place } from "./parts"

/** Hour labels above the tracks, clear of the day column, pinned under the bar. */
export function TimeAxis({ ticks }: { ticks: Tick[] }) {
  return (
    <div
      aria-hidden
      className="sticky top-bar z-10 hidden border-b border-ink bg-screen pl-day md:block"
    >
      <div className="relative h-8">
        {ticks.map((t) => (
          <span
            key={t.label}
            className="absolute bottom-1 -translate-x-1/2 text-xs text-grain"
            style={{ left: `${t.left * 100}%` }}
          >
            {t.label}
          </span>
        ))}
      </div>
    </div>
  )
}

/**
 * A day's numeral and weekday: centred beside its track, or on phones pinned
 * under the bar while its day scrolls by. Today is inverted, as a picked day is.
 */
export function DayCell({
  number,
  weekday,
  today,
  quiet = false,
}: {
  number: string
  weekday: string
  today: boolean
  quiet?: boolean
}) {
  return (
    <div
      aria-current={today ? "date" : undefined}
      className={cn(
        "border-r border-ink md:flex md:flex-col md:justify-center",
        today ? "bg-ink text-screen" : quiet && "text-grain"
      )}
    >
      <div className="sticky top-bar flex flex-col py-2 md:static">
        <span className="title text-2xl md:text-3xl">{number}</span>
        <span className={cn("text-xs text-grain", today && "text-screen/70")}>
          {weekday}
        </span>
      </div>
    </div>
  )
}

/** One lane of a day: faint hour lines, blocks placed on them, and now. */
export function Track({
  ticks,
  now,
  className,
  children,
  ...rest
}: { ticks: Tick[]; now?: number | null } & ComponentProps<"div">) {
  return (
    <div className={cn("relative h-24", className)} {...rest}>
      {ticks.map((t) => (
        <span
          key={t.label}
          aria-hidden
          className="absolute inset-y-0 border-l border-haze"
          style={{ left: `${t.left * 100}%` }}
        />
      ))}
      {children}
      {now != null && (
        <span
          aria-hidden
          className="pointer-events-none absolute inset-y-0 w-px bg-ink"
          style={{ left: `${now * 100}%` }}
        />
      )}
    </div>
  )
}

/** A Screening on its track, width by running time. `className` sets its tone. */
export function TrackBlock({
  block: b,
  className,
  lead,
  ticketLabel = "Ticket",
  ticketClassName,
}: {
  block: TrackBlockVM
  className?: string
  /** Before the title, such as a + or −. */
  lead?: ReactNode
  ticketLabel?: string
  ticketClassName?: string
}) {
  return (
    <Link
      to={b.href}
      className={cn(
        "absolute inset-y-2 flex flex-col justify-between overflow-hidden px-2 py-1",
        className
      )}
      style={{ left: `${b.left * 100}%`, width: `${b.width * 100}%` }}
    >
      <span className="flex gap-1 text-sm leading-tight font-medium">
        {lead && <span className="flex h-lh items-center">{lead}</span>}
        <span className="line-clamp-2">{b.title}</span>
      </span>
      {/* Start and end at the edges they mark; the place gives way between. */}
      <span className="flex items-center gap-1 text-xs">
        <span className="shrink-0">
          {/* On the baseline, moved down to centre on the figures. A transform, as
              vertical-align snaps to whole pixels. */}
          {b.ticket && (
            <TicketIcon
              size="1.1em"
              weight="bold"
              aria-label={ticketLabel}
              className={cn(
                "mr-1 inline translate-y-[0.21em] align-baseline",
                ticketClassName
              )}
            />
          )}
          {b.time}
        </span>
        <Place venue={b.venue} auditorium={b.auditorium} className="truncate" />
        <span className="ml-auto shrink-0 pl-1">{b.end}</span>
      </span>
    </Link>
  )
}
