# Where a prompt's answer lands, per claude-chat-flow.md: a square born as
# the prompt bar's exact rectangle, that flies to the top-right corner and
# becomes a real chat - transcript plus composer, not a one-shot answer.
# Docked, it stays fully open until explicitly minimized (see
# claudeEdgeDockState.py / claudeEdgeDockAnimation.py / claudeEdgeTrigger.py)
# - no automatic retreat - and a TAB peek lets it be reopened once hidden.
#
# design.md / claude-chat-flow.md: the card must NOT be a child of the
# overlay - the ring closes as soon as the prompt is sent, so the card is
# its own top-level window, and ChatSlot is what keeps it alive afterwards.
#
# Per ADR-0007, split into this view (widgets, paint/input, orchestration),
# claudeChatCardState.py (session/turn data, no Qt) and
# claudeChatCardAnimation.py (every Clock/Tween, the edge-dock driver/
# trigger, and the tick-fed radius/tilt) - ChatCard keeps its previous
# attribute surface via thin properties so callers outside this file don't
# need to know the split happened.

from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QPlainTextEdit, QScrollArea,
    QVBoxLayout, QHBoxLayout, QLayout, QApplication,
)
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics, QPalette, QCursor
from PySide6.QtCore import Qt, QRectF, QTimer, QVariantAnimation, Signal

import cardStore
import chatMarkdown
import dockCorner
import screenshot
import style
import timetable
import vaultSearch
from floatingCard import paint_card_bands
from dueList import DueList
from breakdownBlock import BreakdownBlock
from notePicker import NotePicker
from anims import curves
from claudeChatCardState import ChatCardState
from claudeChatCardAnimation import ChatCardAnimation
from claudeEdgeDockState import OPEN
from util import reduced_motion

STORE_KEY = "chat"

COMMAND_PREFIX = "!"

SHOT_SETTLE_MS = 120  # for the card to actually leave the screen before it is grabbed
SHOT_TRANSCRIPT_HEIGHT = 96


def command_name(text):
    """The command of a `! today`-style chat message, or None if the message
    is normal chat. A bare "!" is normal chat, same as a bare "?"."""
    if not text.startswith(COMMAND_PREFIX):
        return None
    return text[len(COMMAND_PREFIX):].strip().casefold() or None


class Composer(QPlainTextEdit):
    """Present from the moment the card lands - no mode switch between
    reading and asking. Enter sends, Shift+Enter newlines, Escape blurs the
    field rather than closing the card."""

    submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(style.CHAT_COMPOSER_HEIGHT)
        self.setPlaceholderText("ask anything")
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTabChangesFocus(True)
        self.setFrameShape(QPlainTextEdit.NoFrame)
        self.setStyleSheet(style.plain_field_stylesheet())
        palette = self.palette()
        palette.setColor(QPalette.PlaceholderText, QColor(style.MUTED))
        self.setPalette(palette)

        # QPlainTextEdit lays its document out from the top, not centered -
        # zero its own document margin and inset the viewport by whatever's
        # left over from the one line of text, so it sits centered in the
        # fixed composer height instead of hugging the top.
        self.ensurePolished()  # forces the stylesheet's font onto self.font() now, not on first show
        self.document().setDocumentMargin(0)
        pad = max(0, (style.CHAT_COMPOSER_HEIGHT - QFontMetrics(self.font()).height()) // 2)
        self.setViewportMargins(0, pad, 0, pad)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.clearFocus()
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            text = self.toPlainText().strip()
            if text:
                self.submitted.emit(text)
                self.clear()
            return
        super().keyPressEvent(event)


class ChatCard(QWidget):
    dismissed = Signal(object)
    corner_changed = Signal(str)

    def __init__(self, born, dock_rect, screen, corner=dockCorner.TOP_RIGHT):
        super().__init__(None)  # top-level: it outlives the overlay it came from
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)  # never yank focus off whatever the user is doing

        self.state = ChatCardState(dock_rect, corner)
        self.streaming_label = None
        self.streaming_index = None
        self.auto_scroll = True
        self.focus_composer_on_land = False
        self.lookup = None  # the `?` lookup or `!` command in flight, if any (card.md)
        self.lookup_factory = vaultSearch.ExplainQuery  # swappable in tests, so no real vault or `claude` subprocess
        self.resolve_factory = vaultSearch.ResolveRequest  # swappable in tests, so no real QThread
        self.notes_factory = vaultSearch.NotesQuery  # swappable in tests, so no real vault index
        self.calendar_factory = timetable.CalendarQuery  # swappable in tests, so no real fetch
        self.picker = None  # the latest lookup's note picker, if it got one
        self.maybe_block = None  # the latest lookup's "you've written about this" block, if it got one
        self.breakdown_block = None  # the latest sentence lookup's breakdown, if it got one
        self.breakdown_request = None  # its off-thread resolve, while that is still in flight
        self.due_list = None  # the latest `! today` / `! week`'s "what is due" box, if it had events
        self.selector = None  # the `! ss` region selector, while it is open
        self.attachment = None  # (path, pixmap) of the screenshot waiting to ride on the next chat message

        self.buildContent()
        self.setContent(False)

        self.animation = ChatCardAnimation(self, self.state, born, screen, not reduced_motion())

    # --- thin forwarding to state/animation, for callers outside this file ---

    @property
    def dock_rect(self):
        return self.state.dock_rect

    @property
    def corner(self):
        return self.state.corner

    @property
    def wedge_id(self):
        return self.state.wedge_id

    @wedge_id.setter
    def wedge_id(self, value):
        self.state.wedge_id = value

    @property
    def action(self):
        return self.state.action

    @action.setter
    def action(self, value):
        self.state.action = value

    @property
    def session_id(self):
        return self.state.session_id

    @property
    def request(self):
        return self.state.request

    @property
    def turns(self):
        return self.state.turns

    @property
    def radius(self):
        return self.animation.radius

    @property
    def tilt(self):
        return self.animation.tilt

    @property
    def edge_driver(self):
        return self.animation.edge_driver

    @property
    def edge_trigger(self):
        return self.animation.edge_trigger

    @property
    def born(self):
        return self.animation.born

    @property
    def flight(self):
        return self.animation.flight

    @property
    def fade(self):
        return self.animation.fade

    @property
    def motion(self):
        return self.animation.motion

    @motion.setter
    def motion(self, value):
        self.animation.motion = value

    def buildContent(self):
        self.header_label = QLabel("Bel", self)
        header_font = QFont(style.CHAT_MONO_FAMILY)
        header_font.setPointSizeF(style.CHAT_HEADER_SIZE)
        header_font.setLetterSpacing(QFont.PercentageSpacing, style.CHAT_HEADER_TRACKING_PERCENT)
        self.header_label.setFont(header_font)
        self.header_label.setStyleSheet(f"color: {style.CHAT_LABEL_MONO}; background: transparent;")
        # Lets a press pass through to the card's own mousePressEvent below
        # instead of being swallowed here - the header is the drag-to-corner
        # zone (same "margins pass through, buttons don't" split as notes',
        # noteCard.py's own header_label).
        self.header_label.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.minimize_button = QPushButton("−", self)
        self.minimize_button.setFixedSize(18, 18)
        self.minimize_button.setCursor(Qt.PointingHandCursor)
        self.minimize_button.setStyleSheet(style.chat_close_stylesheet())
        self.minimize_button.clicked.connect(self.minimize)

        self.close_button = QPushButton("✕", self)
        self.close_button.setFixedSize(18, 18)
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setStyleSheet(style.chat_close_stylesheet())
        self.close_button.clicked.connect(self.dismiss)

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(self.header_label)
        header.addStretch(1)
        header.addWidget(self.minimize_button)
        header.addWidget(self.close_button)

        self.transcript = QWidget()
        self.transcript_layout = QVBoxLayout(self.transcript)
        # QVBoxLayout(self.transcript) makes this the transcript widget's own
        # top-level layout, which (unlike header's nested QHBoxLayout, which
        # defaults to 0) picks up the style's default ~9px margins on all 4
        # sides unless overridden. Left/right zeroed so turn text lines up
        # with the header label's and composer's own left edge; top/bottom
        # kept as an explicit SPACE_2 (matching the gap already used just
        # outside the scroll area, on both sides of it) rather than leaving
        # the vertical cushion to that same implicit default.
        self.transcript_layout.setContentsMargins(0, style.SPACE_2, 0, style.SPACE_2)
        self.transcript_layout.setSpacing(style.SPACE_2)
        self.transcript_layout.addStretch(1)  # keeps a short transcript bottom-anchored

        self.scroll = QScrollArea(self)
        self.scroll.setWidget(self.transcript)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setStyleSheet(style.chat_scrollbar_stylesheet())
        # The visible thumb clipped bubble/composer text under it (short
        # single-word bubbles like "idk" worst-hit) - still scrollable via
        # wheel/drag, just no drawn bar. See chat-bubble-polish's follow-up.
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.verticalScrollBar().valueChanged.connect(self.onScrollValueChanged)
        self.scroll.verticalScrollBar().rangeChanged.connect(self.onScrollRangeChanged)

        self.composer = Composer(self)
        self.composer.submitted.connect(self.send)
        # Right edge should line up with the transcript's own rows
        # (contentWidth() - see chat-bubble-polish/04), not root's own
        # raw padded width.
        self.composer.setFixedWidth(self.contentWidth())

        root = QVBoxLayout(self)
        # This card's size is managed entirely by the dock state machine
        # (HIDDEN 64x64, TAB's puck, OPEN style.CHAT_SIZE square), not by Qt - left
        # at Qt's default, activating the layout floors the widget's
        # minimumSize at whatever's visible *at that moment*, and it never
        # shrinks back down again even once content is hidden for a smaller
        # state, silently clamping every setGeometry() call back up to it.
        root.setSizeConstraint(QLayout.SetNoConstraint)
        root.setContentsMargins(*[style.CHAT_PADDING] * 4)
        root.setSpacing(0)
        root.addLayout(header)
        root.addSpacing(style.SPACE_2)
        root.addWidget(self.scroll, 1)
        self.chip = screenshot.ShotChip(self)
        self.chip.cleared.connect(self.clearAttachment)
        self.chip.hide()
        root.addWidget(self.chip)
        # Matches the card's own bottom padding, so the composer sits as far
        # from the transcript above it as from the card's edge below it - see
        # card-visual-polish/03's live-check follow-up.
        root.addSpacing(style.CHAT_PADDING)
        root.addWidget(self.composer)

    def setContent(self, visible):
        for widget in (self.header_label, self.minimize_button, self.close_button, self.scroll, self.composer):
            widget.setVisible(visible)
        self.chip.setVisible(visible and self.attachment is not None)

    def setCompactVisual(self, compact):
        """TAB and HIDDEN show the bare frame only."""
        for widget in (self.header_label, self.minimize_button, self.close_button, self.scroll, self.composer):
            widget.setVisible(not compact)
        self.chip.setVisible(not compact and self.attachment is not None)

    def focusComposerIfPending(self):
        """Shared by the initial flight-landing and every later dock-tween
        landing: reveal()'s `focus=True` sets focus_composer_on_land rather
        than focusing immediately, since a still-hidden/mid-tween composer
        wouldn't hold it."""
        if self.focus_composer_on_land:
            self.focus_composer_on_land = False
            # WA_ShowWithoutActivating keeps this window from ever getting
            # real OS keyboard focus on its own - setFocus() alone would
            # only be Qt-internal. Safe to activate explicitly here since
            # reveal() only reaches this from a wedge pick, which already
            # forced OS foreground for this process (util.force_foreground).
            self.activateWindow()
            self.composer.setFocus()

    # --- the flight from the prompt bar ---

    def fly(self):
        self.setGeometry(self.animation.born.toRect())
        self.show()
        self.raise_()
        if not self.animation.motion:
            self.onLanded()
            return
        self.animation.flight.run(style.CHAT_FLIGHT_MS)

    def onFlightTick(self, ms):
        self.animation.onFlightTick(ms)

    def onLanded(self):
        self.setGeometry(self.state.dock_rect.toRect())
        self.setContent(True)
        self.layout().activate()
        self.animation.land()

        if self.state.buffered:
            self.write(self.state.buffered)
            self.state.buffered = ""
        self.focusComposerIfPending()
        self.update()

    # --- the conversation ---

    def send(self, text):
        if self.state.request is not None or self.lookup is not None or self.state.action is None:
            return
        query = vaultSearch.lookup_query(text)
        if query is not None:
            self.startLookup(text, query)
            return
        command = command_name(text)
        if command == "ss":
            self.startScreenshot()
            return
        if command == "save":
            self.startSave(text)
            return
        if command is not None:
            self.startCommand(text, command)
            return
        shot = self.attachment
        self.clearAttachment()
        self.appendUserTurn(text, shot[1] if shot else None)
        self.streaming_label = self.appendClaudeTurn()
        self.state.streaming_text = ""
        self.composer.setReadOnly(True)
        self.animation.startTyping(self.streaming_label)

        message = text
        if shot:
            message += f"\n\n[The user attached a screenshot at {shot[0]}. Read that image file to see it.]"
        self.state.request = self.state.action(message, session_id=self.state.session_id)
        self.state.request.chunk.connect(self.onChunk)
        self.state.request.session_started.connect(self.onSessionStarted)
        self.state.request.finished.connect(self.onStreamFinished)

    # --- `! ss` ---

    def startScreenshot(self):
        """Nothing goes in the transcript: this only readies an attachment
        for the next message. The card fades out first so it isn't in its
        own shot; the frozen grab is taken before the selector appears."""
        if self.selector is not None:
            return
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        self.setWindowOpacity(0)
        QTimer.singleShot(SHOT_SETTLE_MS, lambda: self.openSelector(screen))

    def openSelector(self, screen):
        frozen = screen.grabWindow(0)
        self.setWindowOpacity(1)
        self.selector = screenshot.RegionSelector(screen, frozen)
        self.selector.selected.connect(self.onShotSelected)
        self.selector.cancelled.connect(self.closeSelector)
        self.selector.open()

    def onShotSelected(self, pixmap):
        try:
            path = screenshot.save(pixmap)
        except OSError:
            self.closeSelector()
            label = self.appendClaudeTurn()
            self.showReply(label, self.streaming_index, "couldn't save the screenshot")
            return
        self.attachment = (path, pixmap)
        self.chip.show_shot(pixmap)
        self.chip.show()
        self.closeSelector()

    def closeSelector(self):
        self.selector.hide()
        self.selector.deleteLater()
        self.selector = None
        self.activateWindow()
        self.composer.setFocus()

    def clearAttachment(self):
        self.attachment = None
        self.chip.hide()

    def onSessionStarted(self, session_id):
        self.state.session_id = session_id

    def onChunk(self, text):
        # Content only streams once the geometry is at rest - text reflowing
        # inside a widget that is still resizing re-hints every glyph.
        if self.animation.flying():
            self.state.buffered += text
        else:
            self.write(text)

    def write(self, text):
        self.animation.stopTyping()
        self.state.streaming_text += text
        self.state.turns[self.streaming_index]["text"] = self.state.streaming_text
        self.setTurnHtml(self.streaming_label, self.state.streaming_text, caret=True)
        QTimer.singleShot(0, self.scrollToBottomIfNeeded)

    def onStreamFinished(self):
        self.animation.stopTyping()  # a reply that finished with zero chunks would otherwise pulse forever
        if self.streaming_label is not None:
            self.setTurnHtml(self.streaming_label, self.state.streaming_text, caret=False)
        self.streaming_label = None
        self.composer.setReadOnly(False)
        self.unwire()

    # --- `?` lookups ---

    def startLookup(self, text, query):
        """A `? query` message searches the vault instead of chatting
        (card.md). It never joins the Claude session, so session_id is left
        alone."""
        self.appendUserTurn(text)
        label = self.appendClaudeTurn()
        index = self.streaming_index
        self.composer.setReadOnly(True)
        self.animation.startTyping(label)
        self.lookup = self.lookup_factory(query, lambda result: self.onLookupResult(query, label, index, result))
        self.lookup.start()

    def onLookupResult(self, query, label, index, result):
        self.animation.stopTyping()
        self.lookup = None
        self.picker = None
        self.maybe_block = None
        self.breakdown_block = None
        self.composer.setReadOnly(False)

        if result["kind"] == "vocab" and result["hit"]:
            text = " — ".join(result["row"])
        elif result["hit"]:
            text = result["content"]
        else:
            text = result["draft"] or "couldn't draft an explanation."
        self.state.turns[index]["text"] = text
        self.setTurnHtml(label, text, caret=False)

        # Only a concept gets a link, and there's nothing to confirm without
        # a draft that could be saved or without a note to put the link in.
        pickable = result["kind"] == "concept" and (
            result["hit"] or (result["draft"] and vaultSearch.is_valid_note_title(query))
        )
        # A new Korean word is offered for saving with Vocab.md as the one
        # row (issue 23). A sentence arrives as kind "sentence", so the kind
        # is the whole gate - is_single_word decides it inside ExplainQuery.
        saveable_word = (
            result["kind"] == "vocab"
            and not result["hit"]
            and result["draft"].strip()
            and result["vocab"] is not None
        )
        # A content match is a maybe, not an answer: whatever the draft and
        # the picker would have done, they still do, and this block only says
        # "you may have written this already" above them. Display-only,
        # because a click here would mean something else entirely from a
        # click in the picker directly below (card.md).
        maybe_written = not result["hit"] and result["kind"] == "concept" and result["content_matches"]
        if maybe_written:
            self.maybe_block = NotePicker(
                result["content_matches"], self.contentWidth(), header="maybe — you've written about this"
            )
            self.maybe_block.lockRows()
            self.showPicker(self.maybe_block)

        if pickable and result["notes"]:
            self.picker = NotePicker(result["notes"], self.contentWidth(), all_notes=result["all_notes"])
            picker = self.picker
            picker.picked.connect(lambda note: self.onNotePicked(picker, query, result, note))
        elif saveable_word:
            self.picker = NotePicker([result["vocab"]], self.contentWidth(), header="new word — save to vocab")
            picker = self.picker
            picker.picked.connect(lambda note: self.onVocabPicked(picker, query, result))
        if self.picker is not None:
            self.showPicker(picker)
        if result["kind"] == "sentence" and result["breakdown"] is not None:
            # Resolved off-thread, so the block can say which words and points
            # are already in the vault without this thread touching the index
            # (korean.md, and see ResolveRequest for why the card owns it).
            self.breakdown_request = self.resolve_factory(result["breakdown"], parent=self)
            self.breakdown_request.finished.connect(self.onBreakdownResolved)
            self.breakdown_request.start()
        QTimer.singleShot(0, self.scrollToBottomIfNeeded)

    def onBreakdownResolved(self, resolved):
        self.breakdown_request = None
        self.breakdown_block = BreakdownBlock(resolved, self.contentWidth())
        block = self.breakdown_block
        block.picked.connect(lambda entry: self.onBreakdownPicked(block, entry))
        self.showPicker(block)

    def onBreakdownPicked(self, block, entry):
        # Confirm-before-write: this is the click, so this is where the row
        # finally reaches the vault. A word files under its lemma, never the
        # surface form - that's the cell resolve_breakdown matched on.
        write = vaultSearch.append_vocab_row if entry["kind"] == "word" else vaultSearch.append_grammar_row
        try:
            write(entry["term"], entry["meaning"])
        except OSError:
            block.showFailed(entry["key"], "couldn't save it")
            return
        block.showSaved(entry["key"])
        QTimer.singleShot(0, self.scrollToBottomIfNeeded)

    def onNotePicked(self, picker, query, result, note):
        try:
            linked = vaultSearch.confirm_pick(query, result, note)
        except (OSError, ValueError):
            picker.showFailed("couldn't save the note")
            return
        if linked is None:
            picker.showFailed("note not found — link skipped")
        else:
            picker.showConnected()
        QTimer.singleShot(0, self.scrollToBottomIfNeeded)

    def onVocabPicked(self, picker, query, result):
        try:
            vaultSearch.append_vocab_row(query, result["draft"].strip())
        except OSError:
            picker.showFailed("couldn't save the word")
            return
        picker.showSaved()
        QTimer.singleShot(0, self.scrollToBottomIfNeeded)

    # --- `! save` ---

    def lastReply(self):
        """The text of Bel's latest reply worth saving, or None. A command's
        output never counts - a `! save` turn least of all, or saving twice
        would file the prompt."""
        for turn in reversed(self.state.turns):
            if turn["role"] == "claude" and turn["text"].strip() and not turn.get("unsaveable"):
                return turn["text"]
        return None

    def startSave(self, text):
        """`! save` files Bel's last reply at the end of a note Derich picks.
        Nothing is written until the click, like every other write here."""
        reply = self.lastReply()
        self.appendUserTurn(text)
        label = self.appendClaudeTurn()
        index = self.streaming_index
        self.state.turns[index]["unsaveable"] = True
        if reply is None:
            self.showReply(label, index, "nothing to save yet")
            return
        self.composer.setReadOnly(True)
        self.animation.startTyping(label)
        self.lookup = self.notes_factory(lambda choices: self.onSaveChoices(label, index, reply, choices))
        self.lookup.start()

    def onSaveChoices(self, label, index, reply, choices):
        self.animation.stopTyping()
        self.lookup = None
        self.composer.setReadOnly(False)
        if not choices["all_notes"]:
            self.showReply(label, index, "couldn't list your notes")
            return
        self.showReply(label, index, "save the last reply to a note")
        picker = NotePicker(
            choices["notes"], self.contentWidth(), header="save the last reply to…", all_notes=choices["all_notes"]
        )
        picker.picked.connect(lambda note: self.onSavePicked(picker, reply, note))
        self.showPicker(picker)

    def onSavePicked(self, picker, reply, note):
        try:
            path = vaultSearch.append_reply(note, reply)
        except (OSError, UnicodeDecodeError):
            picker.showFailed("couldn't save the reply")
            return
        if path is None:
            picker.showFailed("note not found")
        else:
            picker.showSaved()
        QTimer.singleShot(0, self.scrollToBottomIfNeeded)

    # --- `!` commands ---

    def startCommand(self, text, command):
        """A `! today`-style message runs a command instead of chatting.
        Like a `?` lookup, none of them joins the Claude session."""
        self.appendUserTurn(text)
        label = self.appendClaudeTurn()
        index = self.streaming_index
        self.state.turns[index]["unsaveable"] = True  # a command's output isn't a reply to file
        if command in timetable.COMMANDS:
            self.lookup = self.calendar_factory(command, lambda reply: self.onTimetableResult(label, index, reply))
        else:
            self.showReply(label, index, "unknown command — try ! today, ! week, ! save or ! ss")
            return
        self.composer.setReadOnly(True)
        self.animation.startTyping(label)
        self.lookup.start()

    def onCommandResult(self, label, index, reply):
        self.animation.stopTyping()
        self.lookup = None
        self.composer.setReadOnly(False)
        self.showReply(label, index, reply)

    def onTimetableResult(self, label, index, reply):
        """Events show in the "what is due" box in place of the reply text
        (command-styling/01); the text is still the turn's record. Nothing
        on, or a failure, stays words."""
        self.due_list = None
        self.onCommandResult(label, index, reply["text"])
        if reply["boxes"]:
            label.hide()
            self.due_list = DueList(reply["boxes"], self.contentWidth())
            self.showPicker(self.due_list)

    def showPicker(self, picker):
        row = QHBoxLayout()
        row.addWidget(picker)
        row.addStretch(1)
        self.insertTurnRow(row)
        self.animation.popIn(picker)
        QTimer.singleShot(0, self.scrollToBottomIfNeeded)

    def showReply(self, label, index, text):
        self.state.turns[index]["text"] = text
        self.setTurnHtml(label, text, caret=False)
        QTimer.singleShot(0, self.scrollToBottomIfNeeded)

    def unwire(self):
        if self.lookup is not None:
            self.lookup.cancel()
            self.lookup = None
        if self.breakdown_request is not None:
            # Owned here rather than by ExplainQuery: ClaudeQuery.onFinished
            # disconnects from aboutToQuit before calling answered(), so a
            # thread started from there would outlive the app's quit handling.
            self.breakdown_request.cancel()
            self.breakdown_request = None
        if self.state.request is None:
            return
        self.state.request.chunk.disconnect(self.onChunk)
        self.state.request.session_started.disconnect(self.onSessionStarted)
        self.state.request.finished.disconnect(self.onStreamFinished)
        self.state.request = None

    # --- transcript ---

    def appendUserTurn(self, text, shot=None):
        follows_claude = bool(self.state.turns) and self.state.turns[-1]["role"] == "claude"
        self.state.turns.append({"role": "user", "text": text})

        if shot is not None:
            thumb = QLabel()
            thumb.setPixmap(screenshot.thumbnail(shot, SHOT_TRANSCRIPT_HEIGHT))
            thumb.setStyleSheet(f"border: 1px solid {style.CHAT_BORDER}; background: transparent;")
            shot_row = QHBoxLayout()
            if follows_claude:
                shot_row.setContentsMargins(0, style.CHAT_BUBBLE_GAP_EXTRA, 0, 0)
                follows_claude = False  # the gap belongs above the thumbnail, not between it and the bubble
            shot_row.addStretch(1)
            shot_row.addWidget(thumb)
            self.insertTurnRow(shot_row)

        bubble = QLabel(text)
        # Qt.AutoText's rich-text sniff can't fire on html.escape()'d text
        # (it never contains a literal "<tag>" once escaped), so it always
        # renders as plain text anyway - meaning any escaped char (', &, <)
        # showed up as its literal HTML entity instead of decoding back.
        # PlainText makes the escaping unnecessary: nothing here is ever
        # interpreted as markup, whatever the user typed.
        bubble.setTextFormat(Qt.PlainText)
        bubble.setWordWrap(True)
        bubble.setStyleSheet(style.chat_bubble_stylesheet())
        bubble.setFixedWidth(self.userBubbleWidth(text))

        row = QHBoxLayout()
        if follows_claude:
            # Mirrors appendClaudeTurn()'s own follows_user check - see
            # chat-bubble-polish/02's follow-up: the extra gap only widened
            # the user-to-Bel transition, leaving Bel-to-user asymmetric.
            row.setContentsMargins(0, style.CHAT_BUBBLE_GAP_EXTRA, 0, 0)
        row.addStretch(1)
        row.addWidget(bubble)
        self.insertTurnRow(row)

    def appendClaudeTurn(self):
        follows_user = bool(self.state.turns) and self.state.turns[-1]["role"] == "user"
        self.state.turns.append({"role": "claude", "text": ""})
        self.streaming_index = len(self.state.turns) - 1

        label = QLabel("")
        label.setTextFormat(Qt.RichText)
        label.setOpenExternalLinks(True)
        label.setWordWrap(True)
        label.setStyleSheet(style.chat_turn_stylesheet())
        # A word-wrapping QLabel's sizeHint doesn't equal maximumWidth() - Qt
        # computes a narrower "ideal" width from the rich-text layout instead,
        # and the row's trailing addStretch(1) never forces it wider - so the
        # label wrapped at a fraction of the actual available width. Fixed
        # forces it to really use the full content width (minus a deliberate
        # inset - chat-bubble-polish/05 - so it stops short of the composer's
        # own right edge instead of running flush with it).
        label.setFixedWidth(self.replyWidth())

        row = QHBoxLayout()
        if follows_user:
            # transcript_layout's own spacing already separates every turn
            # row uniformly - this widens just the user-bubble-to-Bel-reply
            # transition (appendUserTurn() mirrors this for Bel-to-user),
            # leaving Bel-to-Bel/user-to-user gaps untouched.
            row.setContentsMargins(0, style.CHAT_BUBBLE_GAP_EXTRA, 0, 0)
        row.addWidget(label)
        row.addStretch(1)
        self.insertTurnRow(row)
        return label

    def insertTurnRow(self, row):
        # Before the trailing stretch, so the stretch keeps doing its job of
        # bottom-anchoring a transcript shorter than the frame.
        self.transcript_layout.insertLayout(self.transcript_layout.count() - 1, row)

    def setTurnHtml(self, label, text, caret):
        # QLabel's rich-text engine (Qt.RichText) collapses a literal "\n" to
        # a space instead of breaking the line, unlike the user bubble
        # (plain text) - pre-wrap makes it honor the newlines chatMarkdown
        # joins lines/blocks with, while still word-wrapping.
        body = f'<span style="white-space:pre-wrap;">{chatMarkdown.render(text)}</span>'
        if caret:
            body += f'<span style="color:{style.CHAT_ACCENT};">▏</span>'
        label.setText(body)

    def userBubbleWidth(self, text):
        # A word-wrapping QLabel's sizeHint doesn't equal maximumWidth() (see
        # appendClaudeTurn()'s note), and a plain QFontMetrics guess isn't
        # enough either - QLabel's own word-wrap layout routes through an
        # internal QTextDocument with its own margin QFontMetrics has no
        # visibility into, so a label sized to exactly the text's advance
        # width still wraps a line early. Probe a real label the same way
        # Qt itself will lay the final one out, searching for the narrowest
        # width that doesn't force an extra line, so short messages shrink
        # to fit instead of sitting at bubbleMaxWidth() like Bel's reply
        # always does.
        probe = QLabel(text)
        probe.setTextFormat(Qt.PlainText)  # match the real bubble - AutoText's rich-text sniff would size differently
        probe.setStyleSheet(style.chat_bubble_stylesheet())
        probe.ensurePolished()

        # The binary search below only works when wrapping is possible at
        # all - it detects "too narrow" by watching heightForWidth() grow to
        # a second line. A single unbreakable "word" (no space to wrap on,
        # e.g. "idk") never grows past one line at any width, so that signal
        # never fires and the search would silently collapse to whatever
        # `lo` starts at. Qt's own unwrapped sizeHint() - not a hand-rolled
        # QFontMetrics guess - is the one number guaranteed to already
        # include that same QTextDocument margin, so it's a safe floor
        # whether or not the text can wrap (measured 13px short with a raw
        # QFontMetrics().horizontalAdvance() estimate for single words -
        # exactly this clipped "idk" and other one-word messages).
        probe.setWordWrap(False)
        lo = probe.sizeHint().width()
        hi = self.bubbleMaxWidth()
        if lo >= hi:
            return hi

        probe.setWordWrap(True)
        single_line_height = probe.heightForWidth(hi)
        while lo < hi:
            mid = (lo + hi) // 2
            if probe.heightForWidth(mid) <= single_line_height:
                hi = mid
            else:
                lo = mid + 1
        return lo

    def bubbleMaxWidth(self):
        return round(self.contentWidth() * style.CHAT_BUBBLE_MAX_WIDTH_FRACTION)

    def replyWidth(self):
        return self.contentWidth() - style.CHAT_REPLY_INSET

    def contentWidth(self):
        return style.CHAT_SIZE - 2 * style.CHAT_PADDING

    def onScrollValueChanged(self, value):
        bar = self.scroll.verticalScrollBar()
        self.auto_scroll = value >= bar.maximum() - 2

    def onScrollRangeChanged(self, minimum, maximum):
        if self.auto_scroll:
            self.scroll.verticalScrollBar().setValue(maximum)

    def scrollToBottomIfNeeded(self):
        if self.auto_scroll:
            bar = self.scroll.verticalScrollBar()
            bar.setValue(bar.maximum())

    # --- the edge dock ---

    def onDockStateChanged(self, dock_state):
        self.animation.onDockStateChanged(dock_state)

    def onDockLanded(self):
        self.animation.onDockLanded()

    def minimize(self):
        if self.animation.edge_driver:
            self.animation.edge_driver.minimize()
            self.focus_composer_on_land = False  # tucking it away - a still-pending reveal's focus shouldn't land later

    def reveal(self, focus=False):
        """Picking this card's wedge again while its session is still alive
        just brings it back into view - no new session, no new message.
        `focus` additionally hands the composer the keyboard - deferred to
        onDockLanded() when animated, since onDockStateChanged() itself
        leaves the content hidden mid-tween (see its own comment), and
        focusing a still-hidden composer wouldn't stick."""
        self.raise_()
        if self.animation.edge_driver:
            self.animation.edge_driver.reveal()
        if focus:
            if self.animation.motion:
                self.focus_composer_on_land = True
            else:
                self.activateWindow()  # see focusComposerIfPending()'s comment on WA_ShowWithoutActivating
                self.composer.setFocus()

    def redock(self):
        self.animation.redock()

    def isOnScreen(self):
        return QApplication.screenAt(self.geometry().center()) is not None

    def isTabbed(self):
        return self.animation.isTabbed()

    def isOpen(self):
        return self.animation.isOpen()

    # --- leaving ---

    def stopDynamics(self):
        """Cancel the edge-dock timer and tween - shared by dismiss() and
        ChatSlot.retire(), the two teardown paths, so a stray poll or a
        reveal's still-running tween can't land after teardown starts."""
        self.animation.stopDynamics()

    def dismiss(self):
        if self.animation.fade.state() == QVariantAnimation.Running:
            return
        self.unwire()
        self.stopDynamics()
        if not self.animation.motion:
            self.onFaded()
            return
        self.animation.fade.run(1.0, 0.0, style.CHAT_DISMISS_MS, curves.CHAT_FLIGHT)

    def onFaded(self):
        # Only hide and announce. Tearing the widget down here would destroy
        # the very animation that is still emitting into this slot - the
        # stack holds the card until the event loop has unwound.
        self.hide()
        self.dismissed.emit(self)

    def mousePressEvent(self, event):
        if self.isTabbed():
            if self.animation.tabContains(event.position()) and self.animation.edge_driver:
                self.animation.edge_driver.clickTab()
            return
        if self.isOpen():
            self.animation.dragPress(event.globalPosition())

    def mouseMoveEvent(self, event):
        self.animation.dragMove(event.globalPosition())

    def mouseReleaseEvent(self, event):
        self.animation.dragRelease(event.globalPosition())

    def onCornerChanged(self, corner):
        self.corner_changed.emit(corner)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.dismiss()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        dock_state = self.animation.edge_driver.dock.state if self.animation.edge_driver else None
        if self.isTabbed() or (self.animation.tilt != 0.0 and dock_state != OPEN):
            # Rotation is gated on tilt, not just isTabbed(), so the
            # untilt-back-to-0 animation stays visible after the state has
            # already left TAB - otherwise painting would drop to the
            # unrotated branch the instant TAB ends, and the still-running
            # tilt_tween would keep updating tilt with nothing drawing
            # it, making the tilt appear to vanish instantly. Excluded for
            # OPEN specifically: reopening grows the window to full size
            # while puckRect() stays clamped to its tiny footprint, so
            # keeping this branch there would paint a stuck puck instead of
            # the growing card until the tilt tween finished.
            painter.save()
            pivot = self.animation.tabPivot()
            painter.translate(pivot)
            painter.rotate(self.animation.tilt)
            painter.translate(-pivot.x(), -pivot.y())
            self.paintFrame(painter, self.animation.puckRect())
            painter.restore()
            return

        self.paintFrame(painter, QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))

    def paintFrame(self, painter, frame):
        border = style.CHAT_BORDER_TAB if self.isTabbed() else style.CHAT_BORDER
        radius = self.animation.radius

        if self.scroll.isVisible():
            # Same two-tone body/header/footer treatment as the todo/notes
            # cards, per claude-chat-redesign.md's "matches the todo/notes
            # shell". Skipped for the bare TAB/HIDDEN puck below, which has
            # no header/footer content to band. The seam sits at the scroll
            # area's own bottom edge, not the composer's top - flush with the
            # composer left equal padding above it inside the footer (0px)
            # but not below (CHAT_PADDING), reading as "too high" even though
            # the composer's own position was already symmetric relative to
            # the body - see card-visual-polish/03's live-check follow-up.
            footer_seam = self.scroll.y() + self.scroll.height()
            paint_card_bands(painter, frame, radius, style.CARD_BODY, self.scroll.y(), footer_seam)
            painter.setBrush(Qt.NoBrush)
        else:
            painter.setBrush(QColor(style.CHAT_SURFACE))

        painter.setPen(QPen(QColor(border), 1))
        painter.drawRoundedRect(frame, radius, radius)


class ChatSlot:
    """Holds the one open chat card, if any - only one wedge can ever be
    assigned Claude at a time (settingsCard.py's collision swap), so there
    is never more than one live session to keep track of."""

    def __init__(self):
        self.card = None
        self.closing = []  # torn down on the next event loop turn, not mid-signal
        self.corner = cardStore.load(STORE_KEY, {}).get("corner", dockCorner.TOP_RIGHT)

    def dockRect(self, screen):
        area = screen.availableGeometry()  # work area, not monitor bounds
        return dockCorner.rect(self.corner, area, style.CHAT_SIZE, style.CHAT_MARGIN)

    def onCornerChanged(self, corner):
        self.corner = corner
        cardStore.save(STORE_KEY, {"corner": corner})

    def cardFor(self, wedge_id):
        """The live card if it belongs to this wedge, else None."""
        return self.card if self.card is not None and self.card.wedge_id == wedge_id else None

    def reveal(self, wedge_id):
        """Reselecting a wedge whose session is still alive: bring it back
        into view (and focus the composer) if it's tucked away in HIDDEN/TAB,
        or minimize it if it's already OPEN - a second pick of the same
        wedge tucks it away again rather than ending the session.

        Every pick re-docks the card first, so the wedge is always a way
        back to a visible chat, and an OPEN card nobody can see (off every
        screen) is brought back rather than minimized (chat-card/02)."""
        card = self.cardFor(wedge_id)
        if card is None:
            return False
        visible = card.isOpen() and card.isOnScreen()
        card.redock()
        if visible:
            card.minimize()
        else:
            card.reveal(focus=True)
        return True

    def open(self, born, prompt, wedge_id, action):
        card = self.cardFor(wedge_id)
        if card is not None:
            # Defensive: both callers into beginHandoff() now check reveal()
            # first (ticket 07), so this shouldn't be reachable - routed
            # through reveal() itself rather than a bare card.reveal() so it
            # degrades to the same open/minimize toggle if it ever is.
            self.reveal(wedge_id)
            return card

        # The prompt bar was at the cursor, so its rect picks the monitor.
        screen = QApplication.screenAt(born.center().toPoint()) or QApplication.primaryScreen()
        if self.card is not None:
            self.forget(self.card)

        card = ChatCard(born, self.dockRect(screen), screen, self.corner)
        card.wedge_id = wedge_id
        card.action = action
        card.dismissed.connect(self.forget)
        card.corner_changed.connect(self.onCornerChanged)
        self.card = card

        card.fly()  # before the request starts, so early chunks buffer instead of landing early
        card.send(prompt)
        return card

    def forget(self, card):
        if self.card is card:
            self.card = None
        self.retire(card)

    def retire(self, card):
        """Take a card out of service. It stays referenced until the next
        event loop turn: this can be reached from inside the card's own fade
        animation, and dropping the last reference to the card there would
        destroy that animation mid-emit."""
        card.unwire()
        card.stopDynamics()
        card.hide()
        self.closing.append(card)
        QTimer.singleShot(0, self.dropRetired)

    def dropRetired(self):
        for card in self.closing:
            card.close()
            card.deleteLater()
        self.closing.clear()
