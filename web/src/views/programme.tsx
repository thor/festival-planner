import { Link } from "react-router"

import type { ProgrammeVM } from "@/app/view-models"
import { cn } from "@/lib/utils"

import { Meta, Page } from "./parts"
import { ScreeningRow } from "./screening-row"

export function ProgrammeView({ vm }: { vm: ProgrammeVM }) {
  return (
    <Page>
      <nav aria-label="Days" className="sticky top-10 z-10 flex overflow-x-auto border-x border-b border-ink bg-screen">
        <DayLink href={vm.allHref} current={vm.allCurrent} number="All" weekday="" />
        {vm.days.map((d) => (
          <DayLink key={d.key} href={d.href} current={d.current} number={d.number} weekday={d.weekday} />
        ))}
      </nav>

      {vm.entries.length === 0 ? (
        <p className="py-16 text-xl">Nothing on this day.</p>
      ) : (
        <ol>
          {vm.entries.map((e) => (
            <li
              key={e.id}
              className="grid gap-4 border-b border-ink py-6 md:grid-cols-[1fr_minmax(22rem,30rem)] md:gap-10 md:py-8"
            >
              <div className={cn(e.marks.excluded && "text-grain")}>
                <Link
                  to={e.href}
                  className={cn(
                    "title block text-3xl hover:text-stamp md:text-5xl",
                    e.marks.committed && "text-stamp",
                    e.marks.excluded && "line-through decoration-1",
                  )}
                >
                  {e.title}
                </Link>
                <Meta items={e.meta} className="mt-3" />
              </div>
              <ul className="self-end">
                {e.screenings.map((s) => (
                  <ScreeningRow key={s.id} s={s} />
                ))}
              </ul>
            </li>
          ))}
        </ol>
      )}
    </Page>
  )
}

function DayLink({ href, current, number, weekday }: { href: string; current: boolean; number: string; weekday: string }) {
  return (
    <Link
      to={href}
      aria-current={current ? "page" : undefined}
      className={cn(
        "flex min-w-14 shrink-0 flex-col items-center border-r border-ink px-3 py-2 last:border-r-0 hover:bg-haze",
        current && "bg-ink text-screen hover:bg-ink",
      )}
    >
      <span className="text-xl">{number}</span>
      <span className={cn("text-xs text-grain", current && "text-screen/70")}>{weekday || " "}</span>
    </Link>
  )
}
