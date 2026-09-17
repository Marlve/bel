# `! organize` (.scratch/inbox-organize/issues/01): Claude proposes where
# every `0 Inbox/` note belongs, in one call for the whole Inbox, and Bel
# moves nothing until Derich clicks that note's row in the chat card.
#
# A proposal is more than a top-level folder: the full destination path
# (an existing folder or a new subfolder), a clearer title, related notes to
# link inside it, and the `5 Atlas` hub to list it in. Claude's answer is
# only trusted once checked: the folder must sit under Project, Areas,
# Reference or Archive, and links and hubs must name notes that exist.
# Anything unclear leaves the folder for Derich to pick by hand.
#
# `6 Private/` is never listed, read, sent to Claude, or used as a
# destination - folder_tree walks only the allowed top-level folders, and
# note_titles goes through vaultIndex.iter_markdown_files, which skips
# Private before recursing.

import json
import re
from pathlib import Path

import vaultIndex
import vaultSearch
from actions.claudeAction import ClaudeQuery, ClaudeRequest

ORGANIZE_FOLDERS = ("Project", "Areas", "Reference", "Archive")

RELATED_HEADING = "## Related"
RELATED_LIMIT = 5
NOTE_PROMPT_CHARS = 1500  # keeps the whole prompt well under Windows' command-line limit

ORGANIZE_PROMPT_TEMPLATE = """File each note from the Inbox of an Obsidian vault.

Folder rules: "Project" is content/coding projects only, never school. School units and other ongoing areas go under "Areas" (e.g. Areas/School/<unit>). "Reference" is documents and concept notes. "Archive" is finished work.

For each note, pick the best folder: one from the folder list, or a new subfolder under Project, Areas, Reference or Archive. Suggest a clear title (keep the current one if it's already clear), up to 5 related notes from the note list to link, and the Atlas hub it belongs in (or null).

Reply with only a JSON array, one object per Inbox note:
[{{"note": "<file name>", "folder": "<folder path>", "title": "<title>", "related": ["<note title>"], "atlas": "<hub title or null>"}}]

Folders:
{folders}

Notes:
{titles}

Atlas hubs:
{hubs}

Inbox:
{inbox}"""


def is_allowed_top(name):
    return vaultIndex.folder_name(Path(name)).casefold() in {folder.casefold() for folder in ORGANIZE_FOLDERS}


def folder_tree(vault_path=None):
    """Every folder a note may be filed in, vault-relative with "/"."""
    vault_path = vault_path or vaultIndex.VAULT_PATH
    folders = []
    for top in vault_path.iterdir():
        if not top.is_dir() or not is_allowed_top(top.name):
            continue
        folders.append(top.name)
        for folder in top.rglob("*"):
            relative = folder.relative_to(vault_path)
            if folder.is_dir() and not any(part.startswith(".") for part in relative.parts):
                folders.append(relative.as_posix())
    return sorted(folders)


def note_titles(vault_path=None):
    """The titles of the notes a moved note may link to - every note
    except Inbox's own and the templates."""
    vault_path = vault_path or vaultIndex.VAULT_PATH
    titles = set()
    for path in vaultIndex.iter_markdown_files(vault_path):
        parts = path.relative_to(vault_path).parts
        if len(parts) > 1 and vaultIndex.folder_name(Path(parts[0])).casefold() in {"inbox", "templates"}:
            continue
        titles.add(path.stem)
    return sorted(titles)


def atlas_hubs(vault_path=None):
    vault_path = vault_path or vaultIndex.VAULT_PATH
    try:
        atlas = vaultIndex.resolve_top_folder(vault_path, "Atlas")
    except FileNotFoundError:
        return []
    return sorted(path.relative_to(vault_path).as_posix() for path in atlas.rglob("*.md"))


def build_prompt(entries, folders, titles, hubs):
    inbox = []
    for entry in entries:
        try:
            content = entry.read_text(encoding="utf-8")[:NOTE_PROMPT_CHARS]
        except (OSError, UnicodeDecodeError):
            content = ""
        inbox.append(f"--- {entry.name} ---\n{content}")
    return ORGANIZE_PROMPT_TEMPLATE.format(
        folders="\n".join(folders),
        titles="\n".join(titles),
        hubs="\n".join(Path(hub).stem for hub in hubs) or "(none)",
        inbox="\n\n".join(inbox),
    )


def is_valid_folder_name(name):
    return (
        name not in ("", ".", "..")
        and not name.startswith(".")
        and not name.endswith((".", " "))
        and vaultSearch.is_valid_note_title(name)
    )


def checked_folder(folder, vault_path):
    """`folder` as a real vault-relative path ("2 Areas/School"), matching
    existing folders' names and casing, or None if a note may not go
    there. Its last parts may not exist yet."""
    if not isinstance(folder, str):
        return None
    parts = [part.strip() for part in re.split(r"[\\/]", folder.strip().strip("\\/"))]
    if not all(is_valid_folder_name(part) for part in parts) or not is_allowed_top(parts[0]):
        return None
    try:
        current = vaultIndex.resolve_top_folder(vault_path, vaultIndex.folder_name(Path(parts[0])))
    except FileNotFoundError:
        return None
    names = [current.name]
    for part in parts[1:]:
        existing = None
        if current.is_dir():
            existing = next(
                (child for child in current.iterdir() if child.is_dir() and child.name.casefold() == part.casefold()),
                None,
            )
        current = existing or current / part
        names.append(current.name)
    return "/".join(names)


def free_name(folder, title):
    """`title`, or `title 2`, `title 3`... - the first that isn't already a
    note in `folder`."""
    name = title
    number = 2
    while (folder / f"{name}.md").exists():
        name = f"{title} {number}"
        number += 1
    return name


def answers_by_note(text):
    start, end = text.find("["), text.rfind("]")
    try:
        items = json.loads(text[start:end + 1]) if start != -1 else []
    except ValueError:
        return {}
    if not isinstance(items, list):
        return {}
    answers = {}
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("note"), str):
            answers[item["note"].strip().removesuffix(".md").casefold()] = item
    return answers


def parse_proposals(text, entries, folders, titles, hubs, vault_path=None):
    """One proposal per Inbox entry, from Claude's answer. A proposal's
    folder is None when the answer didn't give a usable one."""
    vault_path = vault_path or vaultIndex.VAULT_PATH
    answers = answers_by_note(text)
    real_titles = {title.casefold(): title for title in titles}
    real_hubs = {Path(hub).stem.casefold(): hub for hub in hubs}
    proposals = []
    for entry in entries:
        answer = answers.get(entry.stem.casefold(), {})

        title = answer.get("title")
        title = title.strip().removesuffix(".md").strip() if isinstance(title, str) else ""
        if not title or not is_valid_folder_name(title):
            title = entry.stem

        folder = checked_folder(answer.get("folder"), vault_path)

        related = []
        wanted = answer.get("related")
        for name in wanted if isinstance(wanted, list) else []:
            real = real_titles.get(name.strip().casefold()) if isinstance(name, str) else None
            if real and real not in related and real.casefold() not in (title.casefold(), entry.stem.casefold()):
                related.append(real)

        atlas = answer.get("atlas")
        atlas = real_hubs.get(atlas.strip().casefold()) if isinstance(atlas, str) else None

        proposals.append({
            "path": entry,
            "folder": folder,
            "new_folder": folder is not None and folder not in folders,
            "title": title,
            "name": free_name(vault_path / folder, title) if folder else title,
            "related": related[:RELATED_LIMIT],
            "atlas": atlas,
        })
    return proposals


def with_line_after_last_bullet(lines, line):
    at = max((index + 1 for index, text in enumerate(lines) if text.lstrip().startswith(("- ", "* ", "+ "))), default=len(lines))
    if at == len(lines) and lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    return lines[:at] + [line] + lines[at:]


def add_to_hub(hub, title):
    """Lists `[[title]]` in an Atlas hub, after its last link, unless it
    already links it."""
    content = hub.read_bytes().decode("utf-8")
    if re.search(rf"\[\[{re.escape(title)}(\]\]|\||#)", content, re.IGNORECASE):
        return
    lines = with_line_after_last_bullet(content.splitlines(keepends=True), f"- [[{title}]]\n")
    hub.write_bytes("".join(lines).encode("utf-8"))


def add_related_links(note, related):
    lines = note.read_bytes().decode("utf-8").splitlines(keepends=True)
    for title in related:
        lines = vaultSearch.with_concept_bullet(lines, title, f"- [[{title}]]\n", section=RELATED_HEADING) or lines
    note.write_bytes("".join(lines).encode("utf-8"))


def organize(proposal, folder, vault_path=None):
    """Files one Inbox note after Derich clicks it: moves it into `folder`
    (creating it if needed) under its proposed title, never overwriting a
    note, then links its related notes and lists it in its Atlas hub.
    Raises ValueError for a folder a note may not go in and OSError when
    the move fails. A failed link after a successful move is reported as
    `linked: False`, since the note has already moved."""
    vault_path = vault_path or vaultIndex.VAULT_PATH
    relative = checked_folder(folder, vault_path)
    if relative is None:
        raise ValueError(f"a note can't be filed in {folder!r}")
    target = vault_path / relative
    # Resolved, so a junction or alias can't lead somewhere else.
    resolved = target.resolve().relative_to(vault_path.resolve())
    if not is_allowed_top(resolved.parts[0]):
        raise ValueError(f"a note can't be filed in {folder!r}")

    source = Path(proposal["path"])
    if not source.is_file():
        # Checked before creating the folder, so a note that's gone since it
        # was listed doesn't leave an empty folder behind.
        raise FileNotFoundError(f"{source} is no longer in the Inbox")
    target.mkdir(parents=True, exist_ok=True)
    destination = target / f"{free_name(target, proposal['title'])}.md"
    source.rename(destination)

    try:
        if proposal["related"]:
            add_related_links(destination, proposal["related"])
        if proposal["atlas"]:
            add_to_hub(vault_path / proposal["atlas"], destination.stem)
    except (OSError, UnicodeDecodeError):
        return {"path": destination, "linked": False}
    return {"path": destination, "linked": True}


class OrganizeQuery(ClaudeQuery):
    """Drives one `! organize` for ChatCard: lists the Inbox, asks Claude
    about all of it at once, and hands `on_result` the proposals plus every
    folder a note may go in (for the rows Derich places by hand). Never
    moves anything itself."""

    def __init__(self, on_result, vault_path=None, request_factory=ClaudeRequest):
        super().__init__(request_factory)
        self.on_result = on_result
        self.vault_path = vault_path or vaultIndex.VAULT_PATH
        self.entries = []
        self.folders = []
        self.titles = []
        self.hubs = []

    def start(self):
        try:
            self.entries = vaultSearch.list_inbox_entries(self.vault_path)
        except FileNotFoundError:
            self.disconnectAboutToQuit()
            self.on_result({"error": "no Inbox folder in the vault"})
            return
        self.folders = folder_tree(self.vault_path)
        if not self.entries:
            self.disconnectAboutToQuit()
            self.on_result({"proposals": [], "folders": self.folders, "failed": False})
            return
        self.titles = note_titles(self.vault_path)
        self.hubs = atlas_hubs(self.vault_path)
        self.ask(build_prompt(self.entries, self.folders, self.titles, self.hubs))

    def answered(self, text, failed):
        proposals = parse_proposals(
            "" if failed else text, self.entries, self.folders, self.titles, self.hubs, vault_path=self.vault_path
        )
        self.on_result({"proposals": proposals, "folders": self.folders, "failed": failed})
