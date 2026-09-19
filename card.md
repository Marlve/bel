# "Which note" — bel chat card reply shape

Picks the vault note a `[[Concept]]` link goes into. Every concept lookup shows this block with the answer, and clicking a note is both the choice and the go-ahead. Nothing is remembered between lookups.

## Trigger

A chat message starting with `?`, e.g. `? Dijkstra`. The text after the prefix is the search term for `search_notes(query)`. Messages without the prefix are normal chat.

## Shape

Bordered inset (`#191A1C` fill, `#232427` border, 7px radius), matching the other reply blocks. Spans the chat's full width (the composer's width) and pops in under the answer: a 220ms fade while rising 8px into place (none with reduced motion).

- Header row: search-style icon + label "ambiguous — confirm the note" (`#E8E8EA`).
- Filter field under the header: the composer's raised fill, placeholder "filter notes…". It only takes focus when clicked, so the composer keeps focus when the block pops in.
- Scrollable list (max ~172px), one row per candidate note, most recently edited first: sand dot for recently-edited, grey dot otherwise, note name, folder path right-aligned in Geist Mono. Rows are split by `1px solid #1D1E21` dividers, last row has none — the same rows as the `! organize` box. While the filter is empty it shows the 20 most recently edited notes. Typing narrows it to every indexed note whose name or folder path contains the text (case-insensitive), still newest first. No match shows a muted "no matching notes" line.
- On pick: the other rows dim, and the picked row gets a smaller, dim second line saying how it went — "connected", or why it didn't — inside the same block, no navigation, no modal.

## Rules

- No buttons besides the rows themselves — clicking a row *is* the action. The filter field locks along with the rows after the first click.
- Shown on every lookup; the pick applies to that lookup only, nothing is saved.
- Candidates come from the vault index, ordered by last edit. Bel can't see which notes are open in Obsidian. The filter searches the list the lookup already fetched, so typing never re-reads the index.
- `6 Private/` notes are never listed.
- `4 Archive/`, `Templates/`, `5 Atlas/` and `3 Reference/` notes aren't listed either. They're still indexed, so a hit still answers from `3 Reference/`, but a link never goes into them.
- Hit (existing `3 Reference/<Concept>.md`): answer from it. Picking a note adds `[[Concept]]` to it.
- Miss: Bel shows its draft explanation above the list. Picking a note is the confirmation — only then is `3 Reference/<Concept>.md` created and `[[Concept]]` added to the picked note. Not picking writes nothing.
- Maybe: a miss whose every word appears in the text of notes that already exist gets a second block, headed "maybe — you've written about this". Up to 5 notes, best match first, no filter field, and the rows are **not clickable** — it's something to notice, not to act on. A click there would mean the opposite of a click in the picker right below it.
- The maybe block warns, it never refuses: whatever the draft and the picker would have done without it, they still do. The match is a loose all-words search, so it will sometimes be wrong, and being unable to file a note is worse than the duplicate it would prevent.
- It sits above the picker when there is one, and shows on its own when there isn't — an unfileable title like `? what is a graph?`, or a draft that failed. Those are the cases with nothing else to offer, so the notes already written are all there is to say.
- The same note can appear in both blocks: "you already wrote about this" and "the link could go here" are different things to say about one note, and dropping it from the picker would stop a link going somewhere legitimate.
- `3 Reference/` notes *are* listed in the maybe block, though they're never picker rows — a duplicate gets filed in Reference, so it's the folder that matters most to a search. Being listed as "you already wrote this" is a different act from being offered as a link target.
- `6 Private/` never appears in the maybe block either. Only concept lookups get one; the Korean flows have their own block.
- The link goes in a `## Concepts` section at the bottom of the picked note, as `- [[Concept]] — gist`. The gist is the first sentence of the Reference note (hit) or the draft (miss), skipping frontmatter and headings, cut at a word to 80 characters with `…`. With no section yet, the heading is appended first. With one, the bullet goes after its last bullet, even if other content follows the section. A concept the section already lists isn't added again, and the pick still says "connected".
- A confirmed write never overwrites an existing note.
- If the picked note was moved or deleted before the pick, the link is skipped.
- Same visual language as the rest of the card: no accent beyond the sand dot, brightness-only hierarchy, no header icon change.
- A new Korean word (single word, not in Vocab.md) gets the same block with the header "new word — save to vocab" and one row, Vocab, with no filter field. Clicking it appends `| word | translation |` to Vocab.md and its second line reads "saved". Sentences are translated but never saved.
