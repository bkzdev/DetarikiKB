# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Detariki Knowledge Base (DKB) — a pipeline that parses the raw game script of「デタリキZ」into a normalized JSON knowledge base, which is the single source of truth. Wiki pages, the knowledge graph, and AI analysis are all generated *from* the knowledge base — they are never hand-authored.

Pipeline: `Raw Script (.dec) → Story Parser → Normalized Story JSON → JSON Schema Validation → AI Extraction / Knowledge Graph / Wiki Generation`.

The project is currently in **Parser Phase 1**: only `agents/parser/` is implemented. `agents/analysis`, `agents/consistency_checker`, `agents/extractor`, `agents/graph_builder`, `agents/orchestrator`, and `agents/wiki_generator` are empty placeholder packages for later phases — do not build them out unless explicitly asked.

Read `AI_CONTEXT.md` first when starting parser work — it is the canonical handoff doc for AI agents on this project and takes priority over this file for parser-specific rules. It is written in Japanese; docs on this project follow a **Japanese-docs / English-code** policy (see below).

## Commands

Environment uses `uv` (Python 3.12, see `pyproject.toml`). Typical local (non-Docker) usage:

```bash
uv sync                          # install deps
uv run pytest                    # run all tests
uv run pytest tests/parser/      # run parser tests only
uv run pytest tests/parser/test_parser_basic.py::test_basic_dialogue  # single test
uv run ruff check .              # lint
uv run ruff format .             # format (Black is not used; ruff format replaces it)
pre-commit run --all-files       # trailing-whitespace, yaml check, ruff, ruff-format
```

Parser pipeline scripts (run from repo root so `agents/` is importable):

```bash
# Detect unknown commands / unregistered character IDs before parsing
python scripts/check_script_compatibility.py data/raw/
python scripts/check_script_compatibility.py data/raw/main/example.dec --output data/reports/

# Raw .dec -> Normalized Story JSON
python scripts/normalize_story.py \
    --input data/raw/main/example.dec \
    --story-id MAIN_S01_C02 --episode-id MAIN_S01_C02_E01 --category MAIN \
    --output data/normalized/main/ \
    --validate --check-compat
```

`check_script_compatibility.py` exit codes are meaningful: `0` compatible, `1` needs_update, `2` blocked — treat non-zero as a signal to update `config/script_commands.yaml` or the character dictionary before trusting parser output on new script batches.

Docker/Dev Container (optional, for Neo4j + Ollama services): `cp .env.example .env && docker compose up -d`, then reopen in VS Code Dev Container. Neo4j Browser on :7474, Ollama API on :11434, MkDocs on :8000. These services are not required for parser work — pytest and the parser scripts run with plain Python.

## Architecture: the Parser (`agents/parser/`)

The parser is a straight-line pipeline of small, single-responsibility modules; understanding the flow across all of them is required before changing any one:

1. **`tokenizer.py`** — turns raw script lines into `ScriptToken`s (`command` `@Foo`, `variable` `$numX=`, `keyword` `msg`/`branch`/`#if`, `text`, `hyphen_option`, `unknown`, etc). Strips control chars, detects Japanese text lines as `TEXT`. This is the only layer that deals with raw line text.
2. **`resolver.py`** (`SpeakerResolver`, `CharacterDictionary`) — tracks speaker-slot state across a script: `$numX`/`$valueX` variable assignments, `@ScenarioCos`/`@ScenarioCosLoad` slot bindings, and `name` forced-name overrides. Resolves a slot/variable to a `Speaker` (with `is_resolved=False` and a "不明人物" placeholder name when the character ID isn't in the dictionary — never dropped).
3. **`parser.py`** (`StoryParser`) — consumes tokens + the resolver to build intermediate `EpisodeData` / `SceneData` / `BlockData` structures. This is where command→block-type decisions live (`DIRECTION_TYPE_MAP`, `STAGE_DIRECTION_COMMANDS`, `CASE_VARIANTS_MAP`, speech command handling for `@ChTalk*` variants, `branch`/`#if`/`#elseif`/`#else`/`#endif` choice-tree building). Currently one episode/one scene per file (Phase 1 scope).
4. **`normalizer.py`** (`Normalizer`, `IdGenerator`) — converts intermediate structures into the final Normalized Story JSON dict matching `schemas/story.schema.json`. Owns ID generation (`{episodeId}_SC001`, `_DLG0001`, `_MONO0001`, `_NAR0001`, `_CHOICE001`, `_STAGE0001`, `_UNKNOWN0001`) and the `compatibilityReport` block.
5. **`exporter.py`** — writes the normalized dict to disk, optionally into category subdirectories (`main/`, `event/`, `raid/`, `other/`, `character/`).

`scripts/normalize_story.py` wires these together as the CLI entry point; `scripts/check_script_compatibility.py` is a standalone, tokenizer-independent scanner (duplicates some regexes) used to vet new script batches against `config/script_commands.yaml` *before* running the real parser.

### Non-obvious invariants (violating these breaks the design intent, not just style)

- **Never discard unrecognized input.** Unknown commands, unresolved character IDs, and unparseable lines become `unknown` blocks or `compatibilityReport` entries — they are reported, never silently dropped. This is a deliberate project rule (see `AI_CONTEXT.md` §13.3).
- **IDs never encode titles.** `storyId`/`episodeId` (e.g. `MAIN_S01_C02_E01`) must stay stable; display titles, ordering, and season/chapter live only in `metadata`/`episode_metadata`, never in the ID string.
- **`reference/parser/story_parse_reference.py` and `characters_reference.json` are read-only references** (from a prior TTS-oriented project), used only to look up character ID mappings or check legacy behavior. Never modify them; new parser logic goes in `agents/parser/`.
- Every block carries a `source` (sourceFile/lineStart/lineEnd/raw/parserRule/confidence) back to the raw script line — this evidence trail is required for all AI-generated content built on top later.
- `config/script_commands.yaml` is the shared command dictionary between the real parser (`agents/parser/parser.py`, hardcoded maps) and the standalone compatibility checker (`scripts/check_script_compatibility.py`, loads the YAML directly) — these two are not currently unified, so a new command must be added to both `config/script_commands.yaml` *and* the relevant map in `parser.py` if it should be parsed into a real block type rather than just detected as "known but unhandled."

### Documentation language policy

Design docs (`docs/architecture/**`, `AI_CONTEXT.md`) are written in Japanese. Code — Python identifiers, JSON keys, schema fields, Neo4j labels, file/directory names, CLI commands, IDs — is English. Follow this split when adding docs or code comments.

### Key reference docs (read before changing parser behavior)

- `docs/architecture/05_Parser/Identifier_Specification.md` — ID format rules (story/episode/scene/block prefixes)
- `docs/architecture/05_Parser/Story_Metadata.md` — where titles/ordering live (never in IDs)
- `docs/architecture/05_Parser/Normalized_Story_JSON.md` — full output schema description
- `docs/architecture/05_Parser/Script_Compatibility_Check.md` — compatibility status rules (`compatible`/`warning`/`needs_update`/`blocked`)
- `docs/architecture/05_Parser/Parser_Implementation_Plan.md` — phase-by-phase implementation plan the current code follows (tokenizer=Phase4, resolver=Phase5, parser=Phase6, normalizer=Phase7, exporter=Phase8, normalize_story.py=Phase9)

Several files under `docs/architecture/01_Project/` and `02_System/` exist but are currently empty placeholders — don't treat their presence as documented content.
