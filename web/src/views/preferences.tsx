import { CheckIcon, MinusIcon, PlusIcon } from "@phosphor-icons/react"
import type { ReactNode } from "react"
import { Link } from "react-router"

import type { DaysVM, PreferencesVM, StepperVM } from "@/app/view-models"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

import { InterestControl } from "./interest"
import { Action, Page, PendingDot } from "./parts"

/** One setting per rule: what it is on the left, the control on the right. */
export function PreferencesView({ vm }: { vm: PreferencesVM }) {
  return (
    <Page>
      <h1 className="sr-only">Preferences</h1>

      <Setting
        title="Days"
        note={
          <span className={cn(!vm.days.every && "text-stamp")}>
            {vm.days.summary}
          </span>
        }
        pending={vm.days.pending}
      >
        <DayStrip days={vm.days} />
        <div className="mt-3 flex min-h-10 flex-wrap items-center justify-between gap-x-4">
          <p id="days-hint" className="text-grain">
            {vm.days.hint}
            <span className="sr-only">
              {" "}
              Hold Shift to choose every day between.
            </span>
          </p>
          {!vm.days.every && (
            <span className="flex items-center gap-2">
              <span className="text-grain">{vm.days.count}</span>
              <Button
                variant="ghost"
                className="h-10 px-3 text-base"
                onClick={vm.days.onEveryDay}
              >
                Every day
              </Button>
            </span>
          )}
        </div>
      </Setting>

      <Setting
        title="Arrive early"
        note="Time to spare before a screening, on top of travel."
      >
        <ul>
          <Stepper s={vm.buffer} />
          {vm.venues.map((v) => (
            <Stepper key={v.label} s={v} />
          ))}
        </ul>
      </Setting>

      <Setting title="Events" note="Talks, Q&As and debates with a screening.">
        <InterestControl vm={vm.events} />
        <label className="mt-6 flex cursor-pointer items-center gap-3 has-[:disabled]:cursor-default has-[:disabled]:opacity-40">
          <input
            type="checkbox"
            checked={vm.attendEvents.on}
            onChange={vm.attendEvents.onToggle}
            className="peer sr-only"
          />
          <span
            aria-hidden
            className={cn(
              "flex size-6 shrink-0 items-center justify-center border border-ink peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-stamp",
              vm.attendEvents.on && "border-stamp bg-stamp text-stamp-ink"
            )}
          >
            {vm.attendEvents.on && <CheckIcon size={16} weight="bold" />}
          </span>
          <span>Keep time for events held after the film</span>
          {vm.attendEvents.pending && <PendingDot />}
        </label>
      </Setting>

      {vm.years.length > 0 && (
        <Setting title="Years" note="Lean towards newer or older films.">
          <ul>
            {vm.years.map((y) => (
              <li
                key={y.year}
                className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-haze py-3 first:border-t-0 first:pt-0"
              >
                <span className="flex items-baseline gap-4">
                  <span className="text-lg">{y.year}</span>
                  <span className="text-grain">{y.films}</span>
                </span>
                <InterestControl vm={y.interest} />
              </li>
            ))}
          </ul>
        </Setting>
      )}

      <Setting
        title="Comparisons"
        note={
          <>
            {vm.comparisons.made}.{" "}
            <Link
              to={vm.comparisons.href}
              className="underline underline-offset-4 hover:text-stamp"
            >
              Compare
            </Link>
          </>
        }
      >
        <InterestControl vm={vm.comparisons.interest} />
      </Setting>
    </Page>
  )
}

function Setting({
  title,
  note,
  pending = false,
  children,
}: {
  title: string
  note: ReactNode
  pending?: boolean
  children: ReactNode
}) {
  return (
    <section
      aria-label={title}
      className="grid grid-cols-[minmax(0,1fr)] gap-5 border-b border-ink py-8 md:grid-cols-[minmax(0,20rem)_minmax(0,1fr)] md:gap-10 md:py-10"
    >
      <header>
        <h2 className="flex items-center gap-3 text-xl">
          {title}
          {pending && <PendingDot />}
        </h2>
        <p className="mt-2 max-w-[34ch] text-grain">{note}</p>
      </header>
      <div className="min-w-0">{children}</div>
    </section>
  )
}

/** The day under a pointer, wherever it has moved to. */
function dayAt(x: number, y: number): string | null {
  const el = document.elementFromPoint(x, y)?.closest<HTMLElement>("[data-day]")
  return el?.dataset.day ?? null
}

/**
 * The Festival Days as a strip that wraps on narrow screens. Press a day and
 * sweep across others to paint a run. Chosen days take the stamp and run
 * together like a strip of film; the rest are struck, like anything else
 * left out.
 */
function DayStrip({ days }: { days: DaysVM }) {
  return (
    <div
      role="group"
      aria-label="Festival Days"
      aria-describedby="days-hint"
      className="grid touch-pan-y grid-cols-[repeat(auto-fit,minmax(3.5rem,1fr))] border-t border-l border-ink select-none"
      onPointerMove={(e) => {
        if (e.buttons === 0) return days.onRelease()
        const day = dayAt(e.clientX, e.clientY)
        if (day) days.onSweep(day)
      }}
      onPointerUp={days.onRelease}
      onPointerCancel={days.onRelease}
      onLostPointerCapture={days.onRelease}
    >
      {days.cells.map((d) => {
        const own = !days.every && d.chosen
        return (
          <button
            key={d.key}
            type="button"
            data-day={d.key}
            aria-pressed={own}
            aria-label={`${d.weekday} ${d.number}`}
            onPointerDown={(e) => {
              if (e.button !== 0) return
              // Keep the moves coming here, even off the strip.
              e.currentTarget.parentElement?.setPointerCapture(e.pointerId)
              days.onPress(d.key, e.shiftKey)
            }}
            onKeyDown={(e) => {
              if (e.key !== "Enter" && e.key !== " ") return
              e.preventDefault()
              days.onPress(d.key, e.shiftKey)
              days.onRelease()
            }}
            className={cn(
              "flex flex-col items-center border-r border-b border-ink py-3 hover:bg-haze focus-visible:relative focus-visible:z-10 focus-visible:-outline-offset-4",
              own && "bg-stamp text-stamp-ink hover:bg-stamp/85",
              own && d.joinsNext && "border-r-stamp",
              !days.every && !d.chosen && "text-grain"
            )}
          >
            <span
              className={cn(
                "text-xl sm:text-2xl",
                !days.every && !d.chosen && "line-through"
              )}
            >
              {d.number}
            </span>
            <span className={cn("text-xs", own ? "opacity-80" : "text-grain")}>
              {d.weekday}
            </span>
          </button>
        )
      })}
    </div>
  )
}

/** Minutes with a step down and up; grain until it is your own. */
function Stepper({ s }: { s: StepperVM }) {
  return (
    <li className="flex items-center justify-between gap-4 border-t border-haze py-2 first:border-t-0 first:pt-0">
      <span
        className={cn(
          "flex min-w-0 items-center gap-3",
          s.usual && "text-grain"
        )}
      >
        <span className="truncate">{s.label}</span>
        {s.pending && <PendingDot />}
      </span>
      <span className="flex items-center">
        {s.onReset && (
          <Button
            variant="ghost"
            className="mr-2 h-10 px-3 text-base text-grain"
            onClick={s.onReset}
          >
            Usual
          </Button>
        )}
        <Action
          icon={MinusIcon}
          label={`${s.label}: 5 min less`}
          onClick={s.onLess}
          className="size-10"
        />
        <span
          className={cn(
            "flex h-10 w-20 items-center justify-center border-y border-ink leading-none",
            s.usual ? "text-grain" : "text-stamp"
          )}
        >
          {s.minutes} min
        </span>
        <Action
          icon={PlusIcon}
          label={`${s.label}: 5 min more`}
          onClick={s.onMore}
          className="size-10"
        />
      </span>
    </li>
  )
}
