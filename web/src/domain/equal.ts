// Structural equality for plain domain values: JSON with sorted keys, so
// field order never matters.

function canonical(value: unknown): string {
  return JSON.stringify(value, (_, v: unknown) =>
    v && typeof v === "object" && !Array.isArray(v)
      ? Object.fromEntries(
          Object.entries(v).sort(([a], [b]) => a.localeCompare(b))
        )
      : v
  )
}

export function sameValue(a: unknown, b: unknown): boolean {
  return canonical(a) === canonical(b)
}
