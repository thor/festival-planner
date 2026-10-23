// Sample programme for the concepts. Real films, made-up screenings.

import type {
  Festival,
  FestivalId,
  FilmId,
  ProgrammeEntry,
  ProgrammeEntryId,
  Screening,
  ScreeningId,
  Venue,
  VenueId,
} from "@/domain/model"

const ZONE = "Europe/Oslo"
const DAY = 86_400_000

/** The next Friday, so the sample is always ahead of you. */
function nextFriday(): Date {
  const today = new Date()
  const d = new Date(
    Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate())
  )
  return new Date(d.getTime() + ((5 - d.getUTCDay() + 7) % 7 || 7) * DAY)
}

const first = nextFriday()
const iso = (d: Date) => d.toISOString().slice(0, 10)

export const festival: Festival = {
  id: "RmVzdGl2YWw6MQ==" as FestivalId,
  slug: "ffs",
  name: "Films from the South",
  startDate: iso(first),
  endDate: iso(new Date(first.getTime() + 9 * DAY)),
  timeZone: ZONE,
}

const venue = (n: number, name: string): Venue => ({
  id: `venue-${n}` as VenueId,
  name,
})

export const venues = [
  venue(1, "Vika"),
  venue(2, "Colosseum"),
  venue(3, "Cinemateket"),
  venue(4, "Saga"),
  venue(5, "Klingenberg"),
]

type Row = [
  title: string,
  year: number,
  country: string,
  minutes: number,
  slots: string[],
]

// Auditoriums by Venue: numbered, named, or unknown (Klingenberg).
const rooms: (string[] | null)[] = [
  ["1", "2", "3", "4", "5", "6"],
  ["1", "2", "3", "4"],
  ["Tancred", "Lillebil"],
  ["1", "2", "3", "4", "5", "6"],
  null,
]
const auditorium = (v: number, n: number) =>
  rooms[v]?.[n % rooms[v].length] ?? null

// Each slot: "day hh:mm venue": day 0 is the opening Friday.
const films: Row[] = [
  ["Sirāt", 2025, "Spain", 115, ["0 18:00 0", "3 21:15 3", "7 14:30 1"]],
  [
    "Sentimental Value",
    2025,
    "Norway",
    133,
    ["0 20:30 1", "2 16:00 0", "8 19:00 1"],
  ],
  ["The Secret Agent", 2025, "Brazil", 158, ["1 19:00 0", "5 17:30 2"]],
  [
    "It Was Just an Accident",
    2025,
    "Iran",
    103,
    ["1 16:15 3", "4 20:00 1", "9 13:00 0"],
  ],
  ["Resurrection", 2025, "China", 160, ["2 19:30 2", "6 18:00 4"]],
  ["Sound of Falling", 2025, "Germany", 155, ["1 21:30 1", "7 18:45 3"]],
  ["No Other Choice", 2025, "South Korea", 139, ["3 18:00 1", "8 21:00 0"]],
  ["Magellan", 2025, "Philippines", 156, ["4 16:00 2", "9 17:00 2"]],
  ["Dry Leaf", 2025, "Georgia", 186, ["5 13:30 4", "8 13:00 2"]],
  ["Romería", 2025, "Spain", 112, ["2 21:45 3", "6 20:45 0"]],
  ["Two Prosecutors", 2025, "Ukraine", 118, ["3 15:30 2", "7 21:00 4"]],
  ["Young Mothers", 2025, "Belgium", 104, ["4 18:15 3", "9 19:30 1"]],
  ["Kontinental '25", 2025, "Romania", 109, ["5 20:15 0", "8 16:30 4"]],
  [
    "Father Mother Sister Brother",
    2025,
    "United States",
    110,
    ["0 15:45 2", "6 15:00 1"],
  ],
  ["The Mastermind", 2025, "United States", 110, ["1 13:30 4", "5 22:00 3"]],
  ["Blue Moon", 2025, "United States", 100, ["2 13:15 1", "7 16:15 0"]],
  ["The Voice of Hind Rajab", 2025, "Tunisia", 89, ["3 19:45 4", "6 17:30 3"]],
  ["Left-Handed Girl", 2025, "Taiwan", 108, ["4 13:45 1", "8 18:30 3"]],
]

/** Wall-clock time in Oslo on festival day `day`, as an instant. */
function instant(day: number, time: string, plusMinutes = 0): string {
  const [h, m] = time.split(":").map(Number)
  const guess = first.getTime() + day * DAY + (h * 60 + m + plusMinutes) * 60000
  const shown = new Date(
    new Date(guess).toLocaleString("en-US", { timeZone: ZONE })
  )
  const asUtc = new Date(
    new Date(guess).toLocaleString("en-US", { timeZone: "UTC" })
  )
  return new Date(guess - (shown.getTime() - asUtc.getTime())).toISOString()
}

export const programme: ProgrammeEntry[] = films
  .map(([title, year, country, minutes, slots], f) => {
    const id = `entry-${f + 1}` as ProgrammeEntryId
    const screenings: Screening[] = slots.map((slot, s) => {
      const [day, time, v] = slot.split(" ")
      return {
        id: `screening-${f + 1}-${s + 1}` as ScreeningId,
        programmeEntryId: id,
        title,
        startTime: instant(Number(day), time),
        endTime: instant(Number(day), time, minutes),
        venue: venues[Number(v)],
        auditorium: auditorium(Number(v), f + s),
        ticketUrl: `https://tickets.example/ffs/${f + 1}-${s + 1}`,
        events:
          f % 4 === 0 && s === 0
            ? [{ description: "Director talk", startTime: null, endTime: null }]
            : [],
        withdrawn: f === 10 && s === 1,
      }
    })
    return {
      id,
      filmId: `film-${f + 1}` as FilmId,
      title,
      year,
      country,
      url: null,
      screenings,
    }
  })
  .sort((a, b) => a.title.localeCompare(b.title))
