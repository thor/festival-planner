import type { ProgrammePort } from "@/domain/ports"

import { festival, programme } from "./seed"

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))

export function memoryProgramme(): ProgrammePort {
  return {
    async festivals() {
      await wait(60)
      return [festival]
    },
    async festival(slug) {
      await wait(60)
      return slug === festival.slug ? festival : null
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
