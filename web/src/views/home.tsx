import { Link } from "react-router"

import type { FestivalVM } from "@/app/view-models"
import { cn } from "@/lib/utils"

import { Wordmark } from "./brand"
import { Page } from "./parts"

export function HomeView({ festivals }: { festivals: FestivalVM[] }) {
  return (
    <Page className="pt-10 md:pt-20">
      <h1>
        <Wordmark className="h-auto w-full max-w-[64rem]" cueClassName="cue" />
      </h1>
      <p className="mt-6 max-w-[32ch] text-xl md:mt-10 md:text-2xl">
        Wander the programme. Keep what moves you. Entr’acte arranges the week
        around it, down to the walk between films.
      </p>

      <h2 className="sr-only">Festivals</h2>
      <ul className="mt-12 border-t border-ink md:mt-20">
        {festivals.map((f) => (
          <li key={f.slug} className="border-b border-ink">
            <Link
              to={f.href}
              className={cn(
                "group grid gap-2 py-6 md:grid-cols-[1fr_auto] md:items-end md:gap-10 md:py-8",
                f.phase === "over" && "text-grain"
              )}
            >
              <span className="title text-3xl group-hover:text-stamp md:text-5xl">
                {f.name}
              </span>
              <span className="tabular-nums md:text-right">
                {f.phase === "now" && <em className="mr-3">On now</em>}
                {f.dates}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Page>
  )
}
