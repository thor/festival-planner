// The day track shared by the Schedule and a Draft: hours across, 10 to 01.

import { TicketIcon } from "@phosphor-icons/react"
import type { ComponentProps, ReactNode } from "react"
import { Link } from "react-router"

import type { Tick, TrackBlockVM } from "@/app/view-models"
import { cn } from "@/lib/utils"

import { Place } from "./parts"

/** Hour labels above the tracks, clear of the day column. */
export function TimeAxis({ ticks }: { ticks: Tick[] }) {
  return (
    <div
      aria-hidden
      className="relative ml-20 hidden h-8 border-b border-ink md:block"
    >
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
  )
}

/** One lane of a day: faint hour lines, blocks placed on them. */
export function Track({
  ticks,
  className,
  children,
  ...rest
}: { ticks: Tick[] } & ComponentProps<"div">) {
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
      <span className="flex items-center gap-1 text-sm leading-tight font-medium">
        {lead}
        <span className="truncate">{b.title}</span>
      </span>
      {/* Only the place gives way when the block is narrow. */}
      <span className="flex items-center gap-1 text-xs">
        <span className="shrink-0">
          {/* Inline, centred on the figures (0.725em tall). */}
          {b.ticket && (
            <TicketIcon
              size="1.1em"
              weight="bold"
              aria-label={ticketLabel}
              className={cn("mr-1 inline align-[-0.19em]", ticketClassName)}
            />
          )}
          {b.time}
        </span>
        <Place venue={b.venue} auditorium={b.auditorium} className="truncate" />
      </span>
    </Link>
  )
}
