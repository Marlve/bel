# "Which note" — bel chat card reply shape

Picks the vault note a `[[Concept]]` link goes into. Every concept lookup shows this block with the answer, and clicking a note is both the choice and the go-ahead. Nothing is remembered between lookups.

## Trigger

A chat message starting with `?`, e.g. `? Dijkstra`. The text after the prefix is the search term for `search_notes(query)`. Messages without the prefix are normal chat.

## Shape

Bordered inset (`#191A1C` fill, `#232427` border, 7px radius), matching the other reply blocks. Spans the chat's full width (the composer's width) and pops in under the answer: a 220ms fade while rising 8px into place (none with reduced motion).

- Header row: search-style icon + label "ambiguous — confirm the note" (`#E8E8EA`).
- Filter field under the header: the composer's raised fill, placeholder "filter notes…". It only takes focus when clicked, so the composer keeps focus when the block pops in.
- Scrollable list (max ~172px), one row per candidate note, most recently edited first: sand dot for recently-edited, grey dot otherwise, note name, folder path right-aligned in Geist Mono. While the filter is empty it shows the 20 most recently edited notes. Typing narrows it to every indexed note whose name or folder path contains the text (case-insensitive), still newest first. No match shows a muted "no matching notes" line.
- On pick: a confirmation row appends below the list — "connected to **[note name]**" with a sand dot — inside the same block, no navigation, no modal.

## Rules

- No buttons besides the rows themselves — clicking a row *is* the action. The filter field locks along with the rows after the first click.
- Shown on every lookup; the pick applies to that lookup only, nothing is saved.
- Candidates come from the vault index, ordered by last edit. Bel can't see which notes are open in Obsidian. The filter searches the list the lookup already fetched, so typing never re-reads the index.
- `6 Private/` notes are never listed.
- `4 Archive/`, `Templates/`, `5 Atlas/` and `3 Reference/` notes aren't listed either. They're still indexed, so a hit still answers from `3 Reference/`, but a link never goes into them.
- Hit (existing `3 Reference/<Concept>.md`): answer from it. Picking a note adds `[[Concept]]` to it.
- Miss: Bel shows its draft explanation above the list. Picking a note is the confirmation — only then is `3 Reference/<Concept>.md` created and `[[Concept]]` added to the picked note. Not picking writes nothing.
- The link goes in a `## Concepts` section at the bottom of the picked note, as `- [[Concept]] — gist`. The gist is the first sentence of the Reference note (hit) or the draft (miss), skipping frontmatter and headings, cut at a word to 80 characters with `…`. With no section yet, the heading is appended first. With one, the bullet goes after its last bullet, even if other content follows the section. A concept the section already lists isn't added again, and the pick still says "connected".
- A confirmed write never overwrites an existing note.
- If the picked note was moved or deleted before the pick, the link is skipped.
- Same visual language as the rest of the card: no accent beyond the sand dot, brightness-only hierarchy, no header icon change.
- A new Korean word (single word, not in Vocab.md) gets the same block with the header "new word — save to vocab" and one row, Vocab, with no filter field. Clicking it appends `| word | translation |` to Vocab.md and shows "saved to **Vocab**". Sentences are translated but never saved.
