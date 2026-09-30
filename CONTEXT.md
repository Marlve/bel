# Bel

A Windows overlay app: a radial pie menu opens on a hotkey, its wedges launch
small always-on-top cards (todo, note, Claude chat, settings).

## Language

**State**:
The finite, named mode a widget is in at a point in time, with named
transitions between values (e.g. the pie menu's `HIDDEN/OPENING/OPEN/...`,
the chat card's edge-dock `OPEN/COMPACT/HIDDEN/TAB`, the prompt bar's
`EMPTY/TYPING/SENDING/REJECTED`). Every stateful widget uses this one word.
_Avoid_: Phase, mode - both were used for this same concept before being
standardized on "state".

**View**:
A widget's Qt-facing half: the widget children it owns, its layout, and its
paint/input event handlers. Owns nothing that ticks on its own.

**Animation**:
A widget's Qt-facing half that owns every `Clock`/`Tween`/`QTimer` it drives,
plus the tick/done callbacks that write into that widget's State. Never
painted directly - it feeds values the View reads.

**Vault**:
Derich's Obsidian vault (`C:\Vault\ObsidianVault`), a second-brain note
collection separate from this repo. Six numbered top-level folders (`0
Inbox` … `5 Atlas`) plus `6 Private` and an unnumbered `Templates/` - the
numeric prefixes are Obsidian file-explorer sort cosmetics only, never
meaningful to matching logic. `6 Private` must never be opened, read, or
listed by Bel under any circumstance.

**Vault index**:
The local SQLite FTS5 full-text index Bel keeps over the vault's markdown
files (`src/vaultIndex.py`, see ADR-0008), refreshed incrementally rather
than rescanned per call. Lives under Bel's own local state
(`~/.bel/vault-index.sqlite3`), never inside the vault folder itself.

**Lookup**:
A chat message prefixed `?` (`? Dijkstra`): Bel searches the vault for the
rest of the message instead of sending it to Claude as normal chat
(`vaultSearch.lookup_query`, `ExplainQuery`).

**Breakdown**:
What a `?` lookup returns for a Korean *sentence* rather than a single word
(`vaultSearch.parse_breakdown`): its translation, one entry per word carrying
the surface form and the dictionary form it files under, and the grammar
points it uses. Resolving it (`resolve_breakdown`) marks each entry with the
`Korean/Vocab.md` or `Korean/Grammar.md` row that already holds it, so a new
entry can be told from a filed one. Resolved off the UI thread
(`ResolveRequest`), because the read contends with the index refresh's write
lock.

**Content match**:
A note whose *text* holds every word of a lookup, found through the vault
index's FTS5 table (`vaultSearch.search_content`). Distinct from a hit, which
matches a note's title exactly and is a certainty answered from the note: a
content match is a **maybe**, shown as its own display-only block so a
reworded question ("? Dijkstra's algorithm") doesn't file a second note about
something already written. It never suppresses the draft.

**Command**:
A chat message prefixed `!` (`! today`, `! week`, `! ss`): Bel runs
that command instead of sending the message to Claude as normal chat, and like
a lookup it never joins the Claude session (`claudeChatCard.command_name`). A
bare `!` is normal chat.

**Screenshot** (`! ss`):
Drag a rectangle on the screen under the cursor; the crop waits as a thumbnail
chip above the composer and rides on the next plain chat message only. It is
saved under `claude.SHOTS_DIR` (inside the CLI's cwd, so no permission prompt)
and the message ends with its path for Claude to read. It runs no request
itself and adds no transcript turn.

**Bel's prompt**:
`claude.BEL_PROMPT`, one literal, appended to every `claude` call - chat, `?`
and the todo wedge alike. Bel is a plain assistant, not a tutor. Its last rule
is what makes one prompt enough: a message that names its own output format
("Reply with only that one word") outranks the usual chat voice.

**Picked note**:
The vault note Derich clicks in a lookup's note picker (`card.md`) - where
the `[[Concept]]` link goes. Chosen per lookup, never remembered. On a miss,
picking a note is also the confirmation that writes the draft
(`vaultSearch.confirm_pick`). Bel has no view onto Obsidian's own editor
state, so the candidates are recently edited indexed notes.
Distinct from `NoteCard` (`src/noteCard.py`), Bel's own sticky-note widget -
not a view onto any actual vault `.md` file.
_Avoid_: Current note - the earlier sticky designation this replaced.
