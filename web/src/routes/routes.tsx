// Routes connect one page hook to one view. Nothing else.

import { Navigate, Outlet, useParams, useSearchParams } from "react-router"

import {
  useComparePage,
  useDraftPage,
  useDraftsPage,
  useFilmPage,
  useFrame,
  useProgrammePage,
  useTicketsPage,
  useTray,
  useWeekPage,
} from "@/app/pages"
import { useFestivals } from "@/app/queries"
import { useSession } from "@/app/session"
import type { Load } from "@/app/view-models"
import { AccountView } from "@/views/account"
import { CompareView } from "@/views/compare"
import { DraftListView, DraftView } from "@/views/drafts"
import { FilmView } from "@/views/film"
import { FrameView } from "@/views/frame"
import { Loading, Missing } from "@/views/parts"
import { ProgrammeView } from "@/views/programme"
import { TicketsView } from "@/views/tickets"
import { TrayView } from "@/views/tray"
import { WeekView } from "@/views/week"

function Show<T>({
  load,
  render,
  back,
}: {
  load: Load<T>
  render: (value: T) => React.ReactNode
  back?: string
}) {
  if (load.state === "loading") return <Loading />
  if (load.state === "missing")
    return <Missing message={load.message} href={back} link="Back" />
  return render(load.value)
}

const useSlug = () => useParams().slug ?? ""

export function Home() {
  const festivals = useFestivals()
  if (festivals.isPending) return <Loading />
  const first = festivals.data?.[0]
  if (!first)
    return (
      <Missing
        message={
          festivals.isError ? "Server unreachable." : "No festivals yet."
        }
      />
    )
  return <Navigate to={`/${first.slug}`} replace />
}

export function Frame() {
  const frame = useFrame(useSlug())
  const session = useSession()
  const tray = useTray(frame.slug)
  return (
    <FrameView
      festival={frame.festival}
      slug={frame.slug}
      letGo={frame.letGo}
      account={
        <AccountView
          signedIn={session.signedIn}
          hint={session.hint}
          onSubmit={session.onSubmit}
          onSignOut={session.signOut}
        />
      }
      tray={<TrayView vm={tray} />}
    >
      <Outlet />
    </FrameView>
  )
}

export function Programme() {
  const [params] = useSearchParams()
  return (
    <Show
      load={useProgrammePage(useSlug(), params.get("day"))}
      render={(vm) => <ProgrammeView vm={vm} />}
    />
  )
}

export function Film() {
  const slug = useSlug()
  return (
    <Show
      load={useFilmPage(slug, useParams().entryId ?? "")}
      back={`/${slug}`}
      render={(vm) => <FilmView vm={vm} />}
    />
  )
}

export function Week() {
  const load = useWeekPage(useSlug())
  if (!load.signedIn) return <Missing message="Sign in to see your week." />
  return <Show load={load} render={(vm) => <WeekView vm={vm} />} />
}

export function Drafts() {
  return (
    <Show
      load={useDraftsPage(useSlug())}
      render={(drafts) => <DraftListView drafts={drafts} />}
    />
  )
}

export function DraftPage() {
  const slug = useSlug()
  return (
    <Show
      load={useDraftPage(slug, useParams().draftId ?? "")}
      back={`/${slug}/drafts`}
      render={(vm) => <DraftView vm={vm} />}
    />
  )
}

export function Compare() {
  const slug = useSlug()
  return (
    <Show
      load={useComparePage(slug)}
      render={(vm) => <CompareView vm={vm} programmeHref={`/${slug}`} />}
    />
  )
}

export function Tickets() {
  return (
    <Show
      load={useTicketsPage(useSlug())}
      render={(vm) => <TicketsView vm={vm} />}
    />
  )
}
