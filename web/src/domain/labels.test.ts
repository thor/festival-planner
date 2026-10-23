import { describe, expect, it } from "vitest"

import { runtimeWord, splitSynopsis } from "./labels"

describe("splitSynopsis", () => {
  it("takes a short last line as who wrote it", () => {
    expect(splitSynopsis("A ghost.\n\nA hotel.\n\nJon Sæter")).toEqual({
      paragraphs: ["A ghost.", "A hotel."],
      credit: "Jon Sæter",
    })
  })

  it("keeps a last sentence as text", () => {
    expect(splitSynopsis("A ghost.\n\nThe end.").credit).toBeNull()
  })

  it("never takes a lone paragraph as a credit", () => {
    expect(splitSynopsis("Short")).toEqual({
      paragraphs: ["Short"],
      credit: null,
    })
  })

  it("has nothing for no text", () => {
    expect(splitSynopsis(null)).toEqual({ paragraphs: [], credit: null })
  })
})

describe("runtimeWord", () => {
  it("reads hours and minutes", () => {
    expect(runtimeWord(78)).toBe("1 h 18 min")
    expect(runtimeWord(45)).toBe("45 min")
    expect(runtimeWord(120)).toBe("2 h")
  })
})
