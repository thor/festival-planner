import type { ProgrammePort } from "@/domain/ports"

import { festival, otherFestivals, programme } from "./seed"

const festivals = [festival, ...otherFestivals]

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))

export function memoryProgramme(): ProgrammePort {
  return {
    async festivals() {
      await wait(60)
      return festivals
    },
    async festival(slug) {
      await wait(60)
      return festivals.find((f) => f.slug === slug) ?? null
    },
    async programme(id) {
      await wait(120)
      return id === festival.id ? programme : []
    },
    async entry(id) {
      await wait(60)
      return programme.find((e) => e.id === id) ?? null
    },
  }
}
