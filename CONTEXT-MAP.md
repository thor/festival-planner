# Context Map

## Contexts

- [Planning](./GLOSSARY.md): festivals, programmes, Schedules, Drafts and Change Sets, Tickets, Seen and Curation, as the backend models them
- [Web](./web/CONTEXT.md): the words the web app shows a User, each standing for a Planning concept

## Relationships

- **Web → Planning**: the web reads and changes Planning only through the GraphQL API (`schema.graphql`). It adds no concepts of its own beyond the Pending Change Set, which becomes a Draft's Change Set when solved.
