import {
  ArrowsLeftRightIcon,
  CalendarBlankIcon,
  FilmStripIcon,
  StackIcon,
  TicketIcon,
} from "@phosphor-icons/react"
import { useState, type ReactNode } from "react"
import { Link } from "react-router"

import { AppIcon } from "./brand"
import { DockContext } from "./dock"
import { NavIcon } from "./parts"

export function FrameView({
  festival,
  slug,
  letGo,
  account,
  tray,
  children,
}: {
  festival: string
  slug: string
  /** Tickets to let go, for the nav count. */
  letGo: number
  account: ReactNode
  tray: ReactNode
  children: ReactNode
}) {
  // Layout only: the dock's node, for pages to render bars into.
  const [dock, setDock] = useState<HTMLElement | null>(null)
  return (
    <div className="min-h-svh">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-screen focus:p-2"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-20 flex h-10 items-stretch border-b border-ink bg-screen">
        <Link
          to="/"
          aria-label="All festivals"
          className="aspect-square h-full shrink-0"
        >
          <AppIcon className="size-full" />
        </Link>
        <Link
          to={`/${slug}`}
          className="hidden min-w-0 flex-1 items-center px-4 text-lg md:flex"
        >
          <span className="truncate">{festival}</span>
        </Link>
        <nav aria-label="Main" className="ml-auto flex">
          <NavIcon to={`/${slug}`} icon={FilmStripIcon} label="Programme" />
          <NavIcon
            to={`/${slug}/schedule`}
            icon={CalendarBlankIcon}
            label="Schedule"
          />
          <NavIcon to={`/${slug}/drafts`} icon={StackIcon} label="Drafts" />
          <NavIcon
            to={`/${slug}/tickets`}
            icon={TicketIcon}
            label="Tickets"
            count={letGo}
            countLabel={`${letGo} to let go`}
          />
          <NavIcon
            to={`/${slug}/compare`}
            icon={ArrowsLeftRightIcon}
            label="Compare"
          />
        </nav>
        {account}
      </header>
      <DockContext value={dock}>
        <div id="main">{children}</div>
      </DockContext>
      <div className="fixed inset-x-0 bottom-0 z-20 flex flex-col">
        <div ref={setDock} className="flex flex-col" />
        {tray}
      </div>
    </div>
  )
}
