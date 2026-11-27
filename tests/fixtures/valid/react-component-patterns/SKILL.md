---
name: react-component-patterns
description: >
  Conventions for writing React components in this codebase, including hooks,
  file naming, and test placement. Use when creating or editing React components
  or reviewing UI pull requests.
paths:
  - "**/*.tsx"
  - "packages/ui/**/*.ts"
disable-model-invocation: false
color: blue
---

# React component patterns

1. Colocate the component, its styles, and its tests in the same folder.
2. Prefer function components and hooks over class components.
3. Keep components focused; extract hooks when stateful logic is reused.
4. Use the ask-questions tool if the design is ambiguous before inventing an API.
