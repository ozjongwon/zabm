# Domain Docs

This repo uses **single-context** domain documentation layout.

## Layout

- **`GLOSSARY.md`** at the repo root: Contains project-wide terminology and definitions
- **`docs/adr/`** directory: Contains Architecture Decision Records (ADRs)

## Consumer Rules

### Reading Domain Docs

1. **Start with `GLOSSARY.md`** for project terminology and concepts
2. **Consult `docs/adr/`** for architectural decisions and their rationales
3. **Use ADR numbering** to find specific decisions (0001-corpus-bounded-support.md, etc.)

### Writing Domain Docs

- **Add new terms to `GLOSSARY.md`** with clear, concise definitions
- **Create ADRs** for significant architectural decisions using the template format
- **Number ADRs sequentially** in the docs/adr/ directory
- **Link ADRs** from relevant code and documentation

### Context Discipline

- Single-context means one set of domain docs for the entire project
- No need for context-specific glossaries or ADRs
- Focus on shared understanding across all development work