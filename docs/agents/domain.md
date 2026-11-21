# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`GLOSSARY.md`** at the repo root, or **`GLOSSARY-MAP.md`** if it exists.
- **`docs/adr/`**: read ADRs that touch the area you're about to work in.

If any of these files don't exist, proceed silently. The `/domain-modeling` skill creates them lazily when terms or decisions are resolved.

## File structure

This is a single-context repository:

```text
/
├── GLOSSARY.md
├── docs/adr/
└── src/
```

## Use the glossary's vocabulary

When output names a domain concept, use the term as defined in `GLOSSARY.md` rather than a synonym the glossary avoids.

If the concept is missing, either reconsider whether the project needs new language or note a real gap for `/domain-modeling`.

## Flag ADR conflicts

If output contradicts an existing ADR, surface the conflict explicitly rather than silently overriding it.
