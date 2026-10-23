import { graphql } from "./graphql"

export const FestivalFields = graphql(`
  fragment FestivalFields on Festival {
    id
    slug
    name
    startDate
    endDate
    timeZone
  }
`)

export const ScreeningFields = graphql(`
  fragment ScreeningFields on Screening {
    id
    startTime
    endTime
    auditorium
    ticketUrl
    withdrawn
    events {
      description
      startTime
      endTime
    }
    venue {
      id
      name
    }
    programmeEntry {
      id
      title
    }
  }
`)

export const EntryFields = graphql(
  `
    fragment EntryFields on ProgrammeEntry {
      id
      title
      year
      country
      url
      tagline
      synopsis
      posterUrl
      stillUrl
      runtimeMinutes
      originalTitle
      director
      genre
      language
      subtitles
      ageLimit
      imdbUrl
      film {
        id
      }
      screenings {
        ...ScreeningFields
      }
    }
  `,
  [ScreeningFields]
)

export const ChangeSetFields = graphql(`
  fragment ChangeSetFields on ChangeSetItem {
    __typename
    ... on AddScreeningCommitment {
      screening {
        id
      }
    }
    ... on ReleaseScreeningCommitment {
      screening {
        id
      }
    }
    ... on AddExcludedScreening {
      screening {
        id
      }
    }
    ... on RemoveExcludedScreening {
      screening {
        id
      }
    }
    ... on AddFilmCommitment {
      programmeEntry {
        id
      }
    }
    ... on ReleaseFilmCommitment {
      programmeEntry {
        id
      }
    }
    ... on AddExcludedProgrammeEntry {
      programmeEntry {
        id
      }
    }
    ... on RemoveExcludedProgrammeEntry {
      programmeEntry {
        id
      }
    }
    ... on RecordComparison {
      preferred {
        id
      }
      other {
        id
      }
    }
    ... on SetProgrammeEntryWeight {
      programmeEntry {
        id
      }
      weight
    }
    ... on SetScreeningWeight {
      screening {
        id
      }
      weight
    }
    ... on SetYearWeight {
      year
      weight
    }
    ... on SetBuffer {
      minutes
      venue {
        id
      }
    }
    ... on SetDateRange {
      startDate
      endDate
    }
    ... on SetEventWeight {
      weight
    }
    ... on SetAttendEvents {
      attend
    }
    ... on SetTransportMode {
      mode
    }
    ... on SetComparisonWeight {
      weight
    }
  }
`)

export const PreferencesFields = graphql(`
  fragment PreferencesFields on Preferences {
    bufferMinutes
    venueBuffers {
      minutes
      venue {
        id
      }
    }
    startDate
    endDate
    programmeEntryWeights {
      programmeEntry {
        id
      }
      weight
    }
    screeningWeights {
      screening {
        id
      }
      weight
    }
    yearWeights {
      year
      weight
    }
    eventWeight
    attendEvents
    transportMode
    comparisonWeight
    comparisons {
      preferred {
        id
      }
      other {
        id
      }
    }
  }
`)

export const DraftFields = graphql(
  `
    fragment DraftFields on Draft {
      id
      status
      stale
      score
      reasons
      notes
      createdAt
      festival {
        id
      }
      changeSet {
        ...ChangeSetFields
      }
      screenings {
        screening {
          ...ScreeningFields
        }
      }
    }
  `,
  [ChangeSetFields, ScreeningFields]
)

export const FestivalsQuery = graphql(
  `
    query Festivals {
      festivals {
        ...FestivalFields
      }
    }
  `,
  [FestivalFields]
)

export const FestivalQuery = graphql(
  `
    query Festival($slug: String!) {
      festival(slug: $slug) {
        ...FestivalFields
      }
    }
  `,
  [FestivalFields]
)

export const ProgrammePageQuery = graphql(
  `
    query ProgrammePage($id: ID!, $after: String) {
      node(id: $id) {
        ... on Festival {
          programmeEntries(first: 100, after: $after) {
            pageInfo {
              hasNextPage
              endCursor
            }
            edges {
              node {
                ...EntryFields
              }
            }
          }
        }
      }
    }
  `,
  [EntryFields]
)

export const EntryQuery = graphql(
  `
    query Entry($id: ID!) {
      node(id: $id) {
        ... on ProgrammeEntry {
          ...EntryFields
        }
      }
    }
  `,
  [EntryFields]
)

export const PlanningQuery = graphql(
  `
    query Planning($festivalId: ID!) {
      viewer {
        tickets {
          exchangeable
          refundable
          screening {
            ...ScreeningFields
          }
        }
        planning(festivalId: $festivalId) {
          activeSchedule {
            id
            number
            score
            acceptedAt
            screenings {
              ...ScreeningFields
            }
          }
          drafts {
            ...DraftFields
          }
          inputs {
            preferences {
              ...PreferencesFields
            }
            screeningCommitments {
              id
            }
            filmCommitments {
              id
            }
            excludedScreenings {
              id
            }
            excludedProgrammeEntries {
              id
            }
          }
          flags {
            kind
            message
            screening {
              ...ScreeningFields
            }
            programmeEntry {
              id
            }
          }
          comparisonSuggestions(limit: 10) {
            scheduled {
              ...EntryFields
            }
            other {
              ...EntryFields
            }
          }
        }
      }
    }
  `,
  [ScreeningFields, DraftFields, EntryFields, PreferencesFields]
)

export const DraftQuery = graphql(
  `
    query Draft($id: ID!) {
      node(id: $id) {
        ... on Draft {
          ...DraftFields
          diff {
            scoreDelta
            added {
              ...ScreeningFields
            }
            removed {
              ...ScreeningFields
            }
            droppedTickets {
              ...ScreeningFields
            }
          }
        }
      }
    }
  `,
  [DraftFields, ScreeningFields]
)

export const CreateDraftMutation = graphql(
  `
    mutation CreateDraft($input: CreateDraftInput!) {
      createDraft(input: $input) {
        __typename
        ... on DraftResult {
          draft {
            ...DraftFields
          }
        }
        ... on InvalidChangeSet {
          problems {
            message
            items
          }
        }
        ... on NotFound {
          message
        }
        ... on NotSignedIn {
          message
        }
      }
    }
  `,
  [DraftFields]
)

export const ResolveDraftMutation = graphql(
  `
    mutation ResolveDraft($input: DraftInput!) {
      resolveDraft(input: $input) {
        __typename
        ... on DraftResult {
          draft {
            ...DraftFields
          }
        }
        ... on InvalidChangeSet {
          problems {
            message
            items
          }
        }
      }
    }
  `,
  [DraftFields]
)

export const AcceptDraftMutation = graphql(
  `
    mutation AcceptDraft($input: DraftInput!) {
      acceptDraft(input: $input) {
        __typename
        ... on ScheduleResult {
          schedule {
            id
            number
            score
            acceptedAt
            screenings {
              ...ScreeningFields
            }
          }
        }
        ... on DraftNotAcceptable {
          message
        }
      }
    }
  `,
  [ScreeningFields]
)

export const DiscardDraftMutation = graphql(`
  mutation DiscardDraft($input: DraftInput!) {
    discardDraft(input: $input) {
      __typename
    }
  }
`)

export const RecordTicketMutation = graphql(`
  mutation RecordTicket($input: RecordTicketInput!) {
    recordTicket(input: $input) {
      __typename
    }
  }
`)

export const RemoveTicketMutation = graphql(`
  mutation RemoveTicket($input: ScreeningInput!) {
    removeTicket(input: $input) {
      __typename
    }
  }
`)
