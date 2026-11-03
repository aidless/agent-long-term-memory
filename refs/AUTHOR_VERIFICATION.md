# Author Verification Checklist (pre-submission gate)

> Generated 2026-11-02. This file records what is **verified** vs **pending manual
> verification** for the 6 references in `references.bib`.
> Reason: the local environment irreversibly sanitizes author names into
> `{{PERSON_*}}` placeholders (they do NOT resolve to real names at compile time).
> We therefore do NOT fabricate names; we leave `AUTHOR_n` placeholders and list
> the verification needed.

## Verified (reliable, no action needed)

| Field | Source | Status |
|-------|--------|--------|
| arXiv ID / title / date for [1]-[5] | arXiv abs pages (fetched 2026-11-02) | ✅ verified |
| DOI / title / year / venue for [6] | OpenAlex API by DOI | ✅ verified |
| ORCID for [6] (3 authors) | ORCID public API | ✅ verified |

## Pending manual verification (BEFORE any submission)

Each `AUTHOR_n` placeholder in `references.bib` must be replaced with the real
author name from the publisher page (arXiv abs page for [1]-[5], MDPI page for [6]).

| Ref | Key | Publisher | # authors | What to check |
|-----|-----|-----------|-----------|---------------|
| [1] | `beyond_pass1_2026` | arXiv:2603.29231 | 3 | author list on abs page |
| [2] | `horizon_gap_2026` | arXiv:2608.06663 | 3 | author list on abs page |
| [3] | `human_inspired_memory_2024` | arXiv:2411.00489 | 10 | author list on abs page |
| [4] | `mosaic_2026` | arXiv:2607.16211 | 6 | author list on abs page |
| [5] | `realm_2026` | arXiv:2609.16053 | 10 | author list on abs page |
| [6] | `self_ref_introspection_2026` | doi:10.3390/e28090951 | 3 | author list on MDPI page |

## ORCID anchors (for [6], to help resolve names if placeholders persist)

- 0000-0001-7402-7482
- 0009-0007-9062-0383
- 0009-0006-9084-8356

## Gate

- **Do NOT submit this paper while any `AUTHOR_n` placeholder remains.**
- The `.bib` compiles cleanly with placeholders, but placeholders are NOT real
  author names and must be resolved before submission.
