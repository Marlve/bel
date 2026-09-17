import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import inboxOrganize


class FakeSignal:
    def __init__(self):
        self.slot = None

    def connect(self, slot):
        self.slot = slot

    def emit(self, *args):
        if self.slot is not None:
            self.slot(*args)


class FakeClaudeRequest:
    def __init__(self, prompt):
        self.prompt = prompt
        self.chunk = FakeSignal()
        self.finished = FakeSignal()
        self.started = False
        self.cancelled = False
        self.failed = False

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True


def write(path, text=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


class VaultTestCase(unittest.TestCase):
    def setUp(self):
        self.vault_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.vault_dir.cleanup)
        self.vault = Path(self.vault_dir.name)
        self.entry = write(self.vault / "0 Inbox" / "Assignment ETW.md", "Report due week 8 for ETW2001.")
        write(self.vault / "1 Project" / "Bel.md", "Overlay app.")
        write(self.vault / "2 Areas" / "School" / "FIT3143" / "Week 3.md", "MPI notes.")
        (self.vault / "3 Reference").mkdir()
        (self.vault / "4 Archive").mkdir()
        self.hub = write(self.vault / "5 Atlas" / "School.md", "- [[Week 3]]\n")
        write(self.vault / "6 Private" / "Secret" / "Hidden.md", "private words")
        write(self.vault / "Templates" / "Study Note.md", "template")

    def answer(self, **fields):
        return json.dumps([{"note": "Assignment ETW.md", **fields}])

    def proposals(self, text):
        entries = [self.entry]
        return inboxOrganize.parse_proposals(
            text,
            entries,
            inboxOrganize.folder_tree(self.vault),
            inboxOrganize.note_titles(self.vault),
            inboxOrganize.atlas_hubs(self.vault),
            vault_path=self.vault,
        )


class VaultListingTests(VaultTestCase):
    def test_the_folder_tree_is_every_folder_a_note_may_go_in(self):
        self.assertEqual(
            inboxOrganize.folder_tree(self.vault),
            ["1 Project", "2 Areas", "2 Areas/School", "2 Areas/School/FIT3143", "3 Reference", "4 Archive"],
        )

    def test_note_titles_leave_out_inbox_templates_and_private(self):
        self.assertEqual(inboxOrganize.note_titles(self.vault), ["Bel", "School", "Week 3"])

    def test_atlas_hubs_are_listed_by_path(self):
        self.assertEqual(inboxOrganize.atlas_hubs(self.vault), ["5 Atlas/School.md"])

    def test_the_prompt_carries_the_inbox_note_and_folders_but_nothing_private(self):
        prompt = inboxOrganize.build_prompt(
            [self.entry],
            inboxOrganize.folder_tree(self.vault),
            inboxOrganize.note_titles(self.vault),
            inboxOrganize.atlas_hubs(self.vault),
        )

        self.assertIn("Report due week 8 for ETW2001.", prompt)
        self.assertIn("2 Areas/School/FIT3143", prompt)
        self.assertNotIn("Private", prompt)
        self.assertNotIn("Hidden", prompt)


class ParseProposalsTests(VaultTestCase):
    def test_an_existing_folder_is_proposed_with_its_title_links_and_hub(self):
        text = "```json\n" + self.answer(
            folder="2 Areas/School/FIT3143", title="ETW Report", related=["Week 3"], atlas="School"
        ) + "\n```"

        [proposal] = self.proposals(text)

        self.assertEqual(
            proposal,
            {
                "path": self.entry,
                "folder": "2 Areas/School/FIT3143",
                "new_folder": False,
                "title": "ETW Report",
                "name": "ETW Report",
                "related": ["Week 3"],
                "atlas": "5 Atlas/School.md",
            },
        )

    def test_a_folder_named_without_its_number_resolves_to_the_real_folder(self):
        [proposal] = self.proposals(self.answer(folder="areas/school"))

        self.assertEqual(proposal["folder"], "2 Areas/School")

    def test_a_new_subfolder_is_allowed_and_marked_new(self):
        [proposal] = self.proposals(self.answer(folder="2 Areas/School/ETW2001"))

        self.assertEqual(proposal["folder"], "2 Areas/School/ETW2001")
        self.assertTrue(proposal["new_folder"])

    def test_folders_outside_the_allowed_ones_are_unclear(self):
        for folder in ("6 Private", "Private/Secret", "0 Inbox", "5 Atlas", "Templates", "../Elsewhere", "2 Areas/../6 Private", "Nowhere", "", None):
            with self.subTest(folder=folder):
                [proposal] = self.proposals(self.answer(folder=folder))
                self.assertIsNone(proposal["folder"])

    def test_a_reply_that_is_not_json_leaves_every_note_unclear(self):
        [proposal] = self.proposals("I'm not sure where this goes.")

        self.assertIsNone(proposal["folder"])
        self.assertEqual(proposal["title"], "Assignment ETW")
        self.assertEqual(proposal["related"], [])
        self.assertIsNone(proposal["atlas"])

    def test_a_note_missing_from_the_reply_is_unclear(self):
        [proposal] = self.proposals(json.dumps([{"note": "Other.md", "folder": "1 Project"}]))

        self.assertIsNone(proposal["folder"])

    def test_an_invalid_title_keeps_the_notes_own_name(self):
        [proposal] = self.proposals(self.answer(folder="1 Project", title="ETW: Report?"))

        self.assertEqual(proposal["title"], "Assignment ETW")

    def test_a_title_given_with_md_drops_the_extension(self):
        [proposal] = self.proposals(self.answer(folder="1 Project", title="ETW Report.md"))

        self.assertEqual(proposal["title"], "ETW Report")

    def test_only_real_notes_are_linked_and_only_real_hubs_are_used(self):
        [proposal] = self.proposals(self.answer(folder="1 Project", related=["week 3", "Made Up", "Hidden"], atlas="Nope"))

        self.assertEqual(proposal["related"], ["Week 3"])
        self.assertIsNone(proposal["atlas"])

    def test_a_name_already_taken_in_the_folder_gets_a_new_name(self):
        [proposal] = self.proposals(self.answer(folder="1 Project", title="Bel"))

        self.assertEqual(proposal["name"], "Bel 2")


class OrganizeTests(VaultTestCase):
    def proposal(self, **fields):
        return {
            "path": self.entry,
            "folder": "2 Areas/School/FIT3143",
            "new_folder": False,
            "title": "Assignment ETW",
            "name": "Assignment ETW",
            "related": [],
            "atlas": None,
            **fields,
        }

    def test_moves_the_note_into_the_folder_under_its_new_title(self):
        outcome = inboxOrganize.organize(self.proposal(title="ETW Report"), "2 Areas/School/FIT3143", vault_path=self.vault)

        destination = self.vault / "2 Areas" / "School" / "FIT3143" / "ETW Report.md"
        self.assertEqual(outcome, {"path": destination, "linked": True})
        self.assertFalse(self.entry.exists())
        self.assertEqual(destination.read_text(encoding="utf-8"), "Report due week 8 for ETW2001.")

    def test_creates_a_new_folder(self):
        outcome = inboxOrganize.organize(self.proposal(), "2 Areas/School/ETW2001", vault_path=self.vault)

        self.assertEqual(outcome["path"], self.vault / "2 Areas" / "School" / "ETW2001" / "Assignment ETW.md")
        self.assertTrue(outcome["path"].exists())

    def test_a_name_clash_never_overwrites(self):
        outcome = inboxOrganize.organize(self.proposal(title="Bel"), "1 Project", vault_path=self.vault)

        self.assertEqual(outcome["path"].name, "Bel 2.md")
        self.assertEqual((self.vault / "1 Project" / "Bel.md").read_text(encoding="utf-8"), "Overlay app.")

    def test_links_related_notes_inside_the_moved_note(self):
        outcome = inboxOrganize.organize(self.proposal(related=["Week 3", "Bel"]), "1 Project", vault_path=self.vault)

        self.assertEqual(
            outcome["path"].read_text(encoding="utf-8"),
            "Report due week 8 for ETW2001.\n\n## Related\n- [[Week 3]]\n- [[Bel]]\n",
        )

    def test_adds_the_note_to_its_atlas_hub(self):
        inboxOrganize.organize(self.proposal(title="ETW Report", atlas="5 Atlas/School.md"), "1 Project", vault_path=self.vault)

        self.assertEqual(self.hub.read_text(encoding="utf-8"), "- [[Week 3]]\n- [[ETW Report]]\n")

    def test_a_hub_that_already_links_the_note_is_left_alone(self):
        write(self.hub, "- [[Week 3]]\n- [[Assignment ETW]]")

        inboxOrganize.organize(self.proposal(atlas="5 Atlas/School.md"), "1 Project", vault_path=self.vault)

        self.assertEqual(self.hub.read_text(encoding="utf-8"), "- [[Week 3]]\n- [[Assignment ETW]]")

    def test_a_hub_without_a_trailing_newline_gets_the_link_on_its_own_line(self):
        write(self.hub, "# School\n- [[Week 3]]")

        inboxOrganize.organize(self.proposal(atlas="5 Atlas/School.md"), "1 Project", vault_path=self.vault)

        self.assertEqual(self.hub.read_text(encoding="utf-8"), "# School\n- [[Week 3]]\n- [[Assignment ETW]]\n")

    def test_a_missing_hub_still_moves_the_note_but_says_linking_failed(self):
        self.hub.unlink()

        outcome = inboxOrganize.organize(self.proposal(atlas="5 Atlas/School.md"), "1 Project", vault_path=self.vault)

        self.assertTrue(outcome["path"].exists())
        self.assertFalse(outcome["linked"])

    def test_a_note_that_is_gone_creates_no_folder(self):
        self.entry.unlink()

        with self.assertRaises(FileNotFoundError):
            inboxOrganize.organize(self.proposal(), "2 Areas/School/ETW2001", vault_path=self.vault)

        self.assertFalse((self.vault / "2 Areas" / "School" / "ETW2001").exists())

    def test_refuses_a_folder_it_may_not_use_and_moves_nothing(self):
        for folder in ("6 Private", "0 Inbox", "5 Atlas", "2 Areas/../6 Private"):
            with self.subTest(folder=folder):
                with self.assertRaises(ValueError):
                    inboxOrganize.organize(self.proposal(), folder, vault_path=self.vault)
                self.assertTrue(self.entry.exists())


class OrganizeQueryTests(VaultTestCase):
    def setUp(self):
        super().setUp()
        self.results = []

    def start(self):
        query = inboxOrganize.OrganizeQuery(self.results.append, vault_path=self.vault, request_factory=FakeClaudeRequest)
        query.start()
        return query

    def test_asks_claude_once_about_the_whole_inbox(self):
        write(self.vault / "0 Inbox" / "Second.md", "Another note.")

        query = self.start()

        self.assertTrue(query.request.started)
        self.assertIn("Report due week 8 for ETW2001.", query.request.prompt)
        self.assertIn("Another note.", query.request.prompt)
        self.assertEqual(self.results, [])

    def test_the_answer_comes_back_as_proposals_and_the_folder_tree(self):
        query = self.start()

        query.request.chunk.emit(self.answer(folder="1 Project"))
        query.request.finished.emit()

        [result] = self.results
        self.assertEqual([proposal["folder"] for proposal in result["proposals"]], ["1 Project"])
        self.assertEqual(result["folders"], inboxOrganize.folder_tree(self.vault))
        self.assertFalse(result["failed"])

    def test_a_failed_answer_leaves_every_note_to_be_placed_by_hand(self):
        query = self.start()

        query.request.chunk.emit(self.answer(folder="1 Project"))
        query.request.failed = True
        query.request.finished.emit()

        [result] = self.results
        self.assertIsNone(result["proposals"][0]["folder"])
        self.assertTrue(result["failed"])

    def test_an_empty_inbox_answers_without_asking_claude(self):
        self.entry.unlink()

        query = self.start()

        self.assertIsNone(query.request)
        self.assertEqual(self.results, [{"proposals": [], "folders": inboxOrganize.folder_tree(self.vault), "failed": False}])

    def test_a_vault_without_an_inbox_says_so(self):
        self.entry.unlink()
        (self.vault / "0 Inbox").rmdir()

        query = self.start()

        self.assertIsNone(query.request)
        self.assertEqual(self.results, [{"error": "no Inbox folder in the vault"}])


if __name__ == "__main__":
    unittest.main()
