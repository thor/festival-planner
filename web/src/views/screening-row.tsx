import {
  MicrophoneStageIcon,
  PlusIcon,
  ShoppingCartSimpleIcon,
  TicketIcon,
  XIcon,
} from "@phosphor-icons/react"

import type { ScreeningVM } from "@/app/view-models"
import { cn } from "@/lib/utils"

import { Action, PendingDot, Place } from "./parts"

export function ScreeningRow({
  s,
  withTicket = false,
}: {
  s: ScreeningVM
  withTicket?: boolean
}) {
  const gone = s.withdrawn || s.marks.excluded
  return (
    <li
      className={cn(
        "grid grid-cols-[4.5rem_3.5rem_1fr_auto] items-center gap-x-3 border-t border-ink py-2 first:border-t-0 md:grid-cols-[5rem_4rem_1fr_auto]",
        gone && "text-grain"
      )}
    >
      <span className={cn(gone && "line-through")}>{s.day}</span>
      <span
        className={cn(
          "text-right",
          s.scheduled && "font-semibold text-stamp",
          gone && "line-through"
        )}
      >
        {s.time}
      </span>
      <span className="flex min-w-0 items-center gap-2">
        {s.withdrawn ? (
          <span className="truncate">Withdrawn</span>
        ) : (
          <Place
            venue={s.venue}
            auditorium={s.auditorium}
            className="truncate"
          />
        )}
        {s.event && (
          <MicrophoneStageIcon
            size={16}
            weight="light"
            aria-label={s.event}
            className="shrink-0"
          >
            <title>{s.event}</title>
          </MicrophoneStageIcon>
        )}
        {s.marks.pending && <PendingDot />}
      </span>
      <span className="flex">
        {withTicket && s.buyHref && (
          <Action
            icon={ShoppingCartSimpleIcon}
            label="Buy ticket"
            href={s.buyHref}
            className="mr-2 border-stamp text-stamp hover:bg-stamp hover:text-stamp-ink dark:border-stamp"
          />
        )}
        <Action
          icon={PlusIcon}
          label={s.marks.committed ? "Release" : "Commit"}
          on={s.marks.committed}
          tone="stamp"
          onClick={s.onCommit}
        />
        <Action
          icon={XIcon}
          label={s.marks.excluded ? "Include" : "Exclude"}
          on={s.marks.excluded}
          onClick={s.onExclude}
          className="-ml-px"
        />
        {withTicket && (
          <Action
            icon={TicketIcon}
            label={s.ticket ? "Remove ticket" : "Add ticket"}
            on={s.ticket}
            tone="stamp"
            onClick={s.onTicket}
            className="-ml-px"
          />
        )}
      </span>
    </li>
  )
}
