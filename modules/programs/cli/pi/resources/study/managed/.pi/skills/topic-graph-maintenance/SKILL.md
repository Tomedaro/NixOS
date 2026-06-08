---
name: topic-graph-maintenance
description: Maintain a Markdown/Obsidian-style graph of topic notes with wikilinks, tags, frontmatter, splits, and index updates.
---
<!-- Managed by modules/programs/cli/pi. Edit the source file there, not the generated runtime copy. -->


# Topic Graph Maintenance Skill

Use when Daniil asks to organize notes, make a knowledge graph, split topics, link concepts, or create maps.

## Workflow
1. Search before creating new notes.
2. Prefer one durable concept per file under `vault/10-topics/`.
3. Use YAML frontmatter: `type`, `status`, `created`, `updated`, `tags`, `related`, `confidence`.
4. Use `[[wikilinks]]` for related concepts.
5. Propose splits when a note becomes too broad.
6. Update `vault/00-index.md` only after review.
7. Never delete or archive without approval.
