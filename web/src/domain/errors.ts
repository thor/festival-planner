// What a port can fail with. Views see these, never transport shapes.

export type PortProblem =
  | { kind: "notSignedIn" }
  | { kind: "notFound" }
  | { kind: "invalidChangeSet"; problems: { message: string; items: number[] }[] }
  | { kind: "draftNotAcceptable"; message: string }
  | { kind: "draftStillSolving" }
  | { kind: "unreachable"; message: string }

export class PortError extends Error {
  readonly problem: PortProblem

  constructor(problem: PortProblem) {
    super(problem.kind)
    this.problem = problem
  }
}

export function problemOf(error: unknown): PortProblem {
  if (error instanceof PortError) return error.problem
  return { kind: "unreachable", message: String(error) }
}

/** Terse words for a problem. */
export function describeProblem(problem: PortProblem): string {
  switch (problem.kind) {
    case "notSignedIn":
      return "Sign in first."
    case "notFound":
      return "Not found."
    case "invalidChangeSet":
      return problem.problems.map((p) => p.message).join(" ")
    case "draftNotAcceptable":
      return "Out of date. Solve again."
    case "draftStillSolving":
      return "Still solving."
    case "unreachable":
      return "Server unreachable."
  }
}
