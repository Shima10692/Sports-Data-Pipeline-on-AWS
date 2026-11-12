# Architecture versions

Every architecture change gets a new version. Old versions are **never overwritten or deleted**.

```
docs/architecture/
  README.md          this file (the rules)
  CHANGELOG.md       one entry per version, newest first
  decisions/         ADRs: why each change was made
  versions/
    v1.0.0/          frozen snapshot: diagram PDFs + VERSION.md
    v1.1.0/          frozen snapshot: diagram PDFs + architecture.md + VERSION.md
```

`docs/architecture.md` and the two PDFs in the project root are the **latest** copies, for convenience. The files under `versions/` are the record and are read-only once written.

## Version numbers

| Bump | When | Example |
|---|---|---|
| **MAJOR** (2.0.0) | A stage is added, removed or replaced; data flow or storage layout changes in a way that breaks downstream | Swap Athena for Redshift; new zone in the lake |
| **MINOR** (1.1.0) | A new option, engine or component inside a stage; a temporary stand-in | Lambda stand-in for Glue (`processing_engine`) |
| **PATCH** (1.1.1) | Labels, notes, layout, typos; no change to what is built | Fix a box label |

## Steps for a change

1. Check the latest version in `CHANGELOG.md`. Make sure its snapshot exists in `versions/`. If not, archive it first.
2. Write an ADR in `decisions/` (context, decision, status, consequences, exit plan if temporary).
3. Update the canvas diagram and `docs/architecture.md`. Stamp the new version on the diagram.
4. Export the diagrams into a **new** `versions/vX.Y.Z/` folder, with a copy of `architecture.md` and a `VERSION.md` (date, summary, files, SHA-256).
5. Add the `CHANGELOG.md` entry.
6. Only then refresh the "latest" copies in the project root.
7. Git: branch `arch/vX.Y.Z-<slug>`, commit, PR, and tag `arch-vX.Y.Z` after merge.

Never edit, rename or delete anything inside `versions/`. A mistake in a snapshot is fixed with a new PATCH version.
