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

**Command**:
A chat message prefixed `!` (`! today`, `! week`, `! organize`, `! socratic`): Bel runs
that command instead of sending the message to Claude as normal chat, and like
a lookup it never joins the Claude session (`claudeChatCard.command_name`). A
bare `!` is normal chat. `! socratic` is the odd one out - it runs no request
at all, only flipping how the next chat turn is asked.

**Socratic mode**:
Off by default; `! socratic` toggles it, and the reply reads the new state
back. On, `claude.SOCRATIC_RULE` is appended to the message sent to the CLI -
the transcript still shows the bare line he typed. In memory only, like
`session_id`, so it starts off every launch.

It rides on the message rather than the system prompt because
`--append-system-prompt` is only honoured when the CLI **creates** a session;
on `--resume` it is ignored and the session keeps the prompt it was born with
(measured 2026-09-18 - a fresh session obeyed an instruction a resumed one
ignored). A system-prompt swap would therefore flip the toggle, print
"socratic mode on", and change nothing about the answer. The message is new
every turn, so the rule reaches a conversation already under way. The same
constraint means `BEL_PROMPT` is fixed for a session's whole life - fine,
since the persona never changes within one.

There is no way to turn socratic mode off by asking (Derich, 2026-09-18): the
rule tells Bel not to give in to "just tell me", because the mode drops
otherwise at exactly the moment it is worth having. `! socratic` is the only
way out.

**Bel's prompt**:
`claude.BEL_PROMPT`, one literal, appended to every `claude` call - chat, `?`,
`! organize` and the todo wedge alike. Bel is a tutor throughout. Its last rule
is what makes one prompt enough: a message that names its own output format
("Reply with only a JSON array", "Reply with only that one word") outranks the
teaching voice. Verified against the real CLI - `! organize` returned clean
JSON and triage a bare "Project" under the tutor persona.

**Picked note**:
The vault note Derich clicks in a lookup's note picker (`card.md`) - where
the `[[Concept]]` link goes. Chosen per lookup, never remembered. On a miss,
picking a note is also the confirmation that writes the draft
(`vaultSearch.confirm_pick`). Bel has no view onto Obsidian's own editor
state, so the candidates are recently edited indexed notes.
Distinct from `NoteCard` (`src/noteCard.py`), Bel's own sticky-note widget -
not a view onto any actual vault `.md` file.
_Avoid_: Current note - the earlier sticky designation this replaced.
