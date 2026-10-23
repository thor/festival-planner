import { ArrowsLeftRightIcon, CalendarBlankIcon, FilmStripIcon, StackIcon } from "@phosphor-icons/react"
import type { ReactNode } from "react"
import { Link } from "react-router"

import { NavIcon } from "./parts"

export function FrameView({
  festival,
  slug,
  account,
  tray,
  children,
}: {
  festival: string
  slug: string
  account: ReactNode
  tray: ReactNode
  children: ReactNode
}) {
  return (
    <div className="min-h-svh">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-screen focus:p-2">
        Skip to content
      </a>
      <header className="sticky top-0 z-20 flex h-10 items-stretch border-b border-ink bg-screen">
        <Link to={`/${slug}`} className="flex min-w-0 flex-1 items-center px-4 text-lg md:px-8">
          <span className="truncate">{festival}</span>
        </Link>
        <nav aria-label="Main" className="flex">
          <NavIcon to={`/${slug}`} icon={FilmStripIcon} label="Programme" />
          <NavIcon to={`/${slug}/week`} icon={CalendarBlankIcon} label="Week" />
          <NavIcon to={`/${slug}/drafts`} icon={StackIcon} label="Drafts" />
          <NavIcon to={`/${slug}/compare`} icon={ArrowsLeftRightIcon} label="Compare" />
        </nav>
        {account}
      </header>
      <div id="main">{children}</div>
      {tray}
    </div>
  )
}
