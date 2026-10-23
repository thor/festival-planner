interface ImportMetaEnv {
  /** "memory" (default) or "graphql". */
  readonly VITE_ADAPTER?: string
  readonly VITE_GRAPHQL_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
