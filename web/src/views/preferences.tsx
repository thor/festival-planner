import { CheckIcon, MinusIcon, PlusIcon } from "@phosphor-icons/react"
import type { ReactNode } from "react"
import { Link } from "react-router"

import type { PreferencesVM, RangeDayVM, StepperVM } from "@/app/view-models"
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
          <span className={cn(vm.limited && "text-stamp")}>{vm.range}</span>
        }
        pending={vm.rangePending}
      >
        <DayStrip days={vm.days} limited={vm.limited} />
        <div className="mt-3 flex min-h-10 items-center justify-between gap-4">
          <p className="text-grain">{vm.rangeHint}</p>
          {vm.limited && (
            <Button
              variant="ghost"
              className="h-10 px-3 text-base"
              onClick={vm.onEveryDay}
            >
              Every day
            </Button>
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

/**
 * The Festival Days as one strip. Days you can go take the stamp once you
 * have chosen; the rest are struck, like anything else left out.
 */
function DayStrip({ days, limited }: { days: RangeDayVM[]; limited: boolean }) {
  return (
    <div className="flex overflow-x-auto border border-ink">
      {days.map((d) => {
        const own = limited && d.inRange
        return (
          <button
            key={d.key}
            type="button"
            onClick={d.onPick}
            aria-pressed={d.inRange}
            aria-label={`${d.weekday} ${d.number}`}
            className={cn(
              "flex min-w-12 flex-1 flex-col items-center border-l border-ink py-3 first:border-l-0 hover:bg-haze focus-visible:relative focus-visible:-outline-offset-4",
              own && "bg-stamp text-stamp-ink hover:bg-stamp/85",
              !d.inRange && "text-grain",
              d.anchor && "shadow-[inset_0_0_0_3px_var(--screen)]"
            )}
          >
            <span
              className={cn(
                "text-xl sm:text-2xl",
                !d.inRange && "line-through"
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
