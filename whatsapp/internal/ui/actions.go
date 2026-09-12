package ui

import (
	"context"
	"fmt"
	"path/filepath"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/UchaBokeria/dotfiles/whatsapp/internal/action"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/domain"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/store"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/vim"
	"github.com/UchaBokeria/dotfiles/whatsapp/internal/wacli"
)

// registerAll populates the action registry.
//
// Every name here is bindable, listable by :actions, and checked by
// configuration validation. Nothing the interface does by key press exists
// outside this table.
func registerAll(r *action.Registry, a *App) {
	reg := func(name, summary string, run func(action.Context) error, opts ...func(*action.Action)) {
		act := action.Action{Name: name, Summary: summary, Run: run}
		for _, o := range opts {
			o(&act)
		}
		r.MustRegister(act)
	}
	repeatable := func(act *action.Action) { act.Repeatable = true }

	// --- navigation ---------------------------------------------------------
	reg("nav.down", "move down", func(c action.Context) error {
		a.navigate(c.EffectiveCount())
		return nil
	})
	reg("nav.up", "move up", func(c action.Context) error {
		a.navigate(-c.EffectiveCount())
		return nil
	})
	reg("nav.left", "move left", func(c action.Context) error {
		if buf, _ := a.activeBuffer(); buf != nil {
			if m := vim.Move(buf, "left", c.EffectiveCount(), 0); m.Valid {
				buf.SetCursor(m.To)
			}
			return nil
		}
		a.focusLeft()
		return nil
	})
	reg("nav.right", "move right", func(c action.Context) error {
		if buf, _ := a.activeBuffer(); buf != nil {
			if m := vim.Move(buf, "right", c.EffectiveCount(), 0); m.Valid {
				buf.SetCursor(m.To)
			}
			return nil
		}
		a.focusRight()
		return nil
	})
	reg("nav.top", "go to the top", func(action.Context) error { a.navTop(); return nil })
	reg("nav.bottom", "go to the bottom", func(action.Context) error { a.navBottom(); return nil })
	reg("nav.half_down", "half a page down", func(c action.Context) error {
		a.navHalfPage(1, c.EffectiveCount())
		return nil
	})
	reg("nav.half_up", "half a page up", func(c action.Context) error {
		a.navHalfPage(-1, c.EffectiveCount())
		return nil
	})
	reg("nav.page_down", "a page down", func(c action.Context) error {
		a.navPage(1, c.EffectiveCount())
		return nil
	})
	reg("nav.page_up", "a page up", func(c action.Context) error {
		a.navPage(-1, c.EffectiveCount())
		return nil
	})
	reg("nav.view_top", "cursor to the top of the view", func(action.Context) error {
		a.pane.Recentre("top")
		return nil
	})
	reg("nav.view_middle", "cursor to the middle of the view", func(action.Context) error {
		a.pane.Recentre("centre")
		return nil
	})
	reg("nav.view_bottom", "cursor to the bottom of the view", func(action.Context) error {
		a.pane.Recentre("bottom")
		return nil
	})
	reg("nav.block_next", "next sender or day", func(c action.Context) error {
		a.navigate(c.EffectiveCount() * 3)
		return nil
	})
	reg("nav.block_prev", "previous sender or day", func(c action.Context) error {
		a.navigate(-c.EffectiveCount() * 3)
		return nil
	})

	reg("view.center", "centre the cursor", func(action.Context) error {
		a.pane.Recentre("centre")
		return nil
	})
	reg("view.top", "cursor line to the top", func(action.Context) error {
		a.pane.Recentre("top")
		return nil
	})
	reg("view.bottom", "cursor line to the bottom", func(action.Context) error {
		a.pane.Recentre("bottom")
		return nil
	})

	// --- panes --------------------------------------------------------------
	reg("pane.toggle", "switch between the conversation and the input",
		func(action.Context) error { a.togglePane(); return nil })
	reg("pane.cycle", "cycle the chat list, conversation and input",
		func(action.Context) error { a.cyclePane(1); return nil })
	reg("pane.cycle_back", "cycle backwards",
		func(action.Context) error { a.cyclePane(-1); return nil })
	// Kept as an alias. An unknown action name stops startup, which is the
	// right behaviour for a typo and the wrong one for a rename: without this,
	// renaming an action would refuse to open for anyone whose config still
	// names the old one.
	reg("pane.toggle_back", "deprecated alias for pane.cycle",
		func(action.Context) error { a.cyclePane(-1); return nil })
	reg("pane.left", "focus the chat list", func(action.Context) error { a.focusLeft(); return nil })
	reg("pane.right", "focus the conversation", func(action.Context) error { a.focusRight(); return nil })
	reg("pane.up", "focus the conversation", func(action.Context) error { a.focusRight(); return nil })
	reg("pane.down", "focus the composer", func(action.Context) error {
		a.setFocus(FocusComposer)
		return nil
	})

	// --- modes --------------------------------------------------------------
	reg("mode.insert", "insert", func(action.Context) error { a.enterInsert(false); return nil })
	reg("mode.insert_after", "insert after the cursor", func(action.Context) error {
		a.enterInsert(true)
		return nil
	})
	reg("mode.insert_line_end", "insert at the end of the line", func(action.Context) error {
		a.enterInsert(false)
		if buf, _ := a.activeBuffer(); buf != nil {
			cur := buf.Cursor()
			buf.SetCursor(vim.Pos{Line: cur.Line, Col: buf.LineLen(cur.Line)})
		}
		return nil
	})
	reg("mode.insert_line_start", "insert at the start of the line", func(action.Context) error {
		a.enterInsert(false)
		if buf, _ := a.activeBuffer(); buf != nil {
			buf.SetCursor(vim.Pos{Line: buf.Cursor().Line})
		}
		return nil
	})
	reg("mode.open_below", "new line below", func(action.Context) error {
		a.enterInsert(false)
		if buf, _ := a.activeBuffer(); buf != nil {
			cur := buf.Cursor()
			buf.SetCursor(vim.Pos{Line: cur.Line, Col: buf.LineLen(cur.Line)})
			buf.Insert("\n")
		}
		return nil
	})
	reg("mode.open_above", "new line above", func(action.Context) error {
		a.enterInsert(false)
		if buf, _ := a.activeBuffer(); buf != nil {
			buf.SetCursor(vim.Pos{Line: buf.Cursor().Line})
			buf.Insert("\n")
			buf.SetCursor(vim.Pos{Line: buf.Cursor().Line - 1})
		}
		return nil
	})
	reg("mode.normal", "normal mode", func(action.Context) error { a.leaveInsert(); return nil })
	reg("mode.visual", "visual mode", func(action.Context) error {
		a.engine.SetMode(vim.Visual)
		return nil
	})
	reg("mode.visual_line", "visual line mode", func(action.Context) error {
		a.engine.SetMode(vim.VisualLine)
		return nil
	})
	reg("mode.cmdline", "command line", func(action.Context) error {
		a.cmdline = ""
		a.completions = nil
		a.editTarget = TargetCmdLine
		a.engine.SetMode(vim.CmdLine)
		return nil
	})
	reg("mode.search_forward", "search forwards", func(action.Context) error {
		a.startFind(true)
		return nil
	})
	reg("mode.search_backward", "search backwards", func(action.Context) error {
		a.startFind(false)
		return nil
	})

	// --- search -------------------------------------------------------------
	reg("search.next", "next match", func(c action.Context) error {
		for i := 0; i < c.EffectiveCount(); i++ {
			if !a.pane.Next(true) {
				a.setStatus("no matches")
				break
			}
		}
		return nil
	})
	reg("search.prev", "previous match", func(c action.Context) error {
		for i := 0; i < c.EffectiveCount(); i++ {
			if !a.pane.Next(false) {
				a.setStatus("no matches")
				break
			}
		}
		return nil
	})
	reg("search.clear", "clear the search highlight", func(action.Context) error {
		// Esc in normal mode does the nearest thing first. With a draft or the
		// search box still editable, that is stepping out of it; otherwise it
		// clears the highlight, as nohlsearch does in Neovim.
		if a.editTarget != TargetNone {
			a.leaveInsert()
			return nil
		}
		a.pane.ClearHighlight()
		a.status = ""
		a.statusErr = false
		return nil
	})
	reg("search.accept", "accept the search", func(action.Context) error { a.acceptFind(); return nil })
	reg("search.cancel", "cancel the search", func(action.Context) error { a.cancelFind(); return nil })
	reg("search.backspace", "delete a character", func(action.Context) error {
		a.findBackspace()
		return nil
	})
	reg("search.delete_word_back", "delete a word", func(action.Context) error {
		a.findLine = deleteWordBack(a.findLine)
		return nil
	})
	reg("search.clear_input", "clear the search prompt", func(action.Context) error {
		a.findLine = ""
		return nil
	})

	// --- selection ----------------------------------------------------------
	reg("select.open", "open", func(action.Context) error {
		switch a.focus {
		case FocusList:
			a.followSelection()
			a.setFocus(FocusChat)
		}
		return nil
	})

	// --- editing ------------------------------------------------------------
	for name, op := range map[string]string{
		"edit.operator_yank":        "yank",
		"edit.operator_delete":      "delete",
		"edit.operator_change":      "change",
		"edit.operator_lower":       "lower",
		"edit.operator_upper":       "upper",
		"edit.operator_toggle_case": "toggle_case",
	} {
		// These never run: the engine intercepts an operator key and enters
		// operator-pending mode. They are registered so the binding validates
		// and so :actions lists them.
		opName := op
		reg(name, "operator: "+opName, func(action.Context) error { return nil }, repeatable)
	}

	reg("edit.delete_char", "delete a character", func(c action.Context) error {
		a.editDeleteChar(c.EffectiveCount())
		return nil
	}, repeatable)
	reg("edit.substitute_char", "replace a character", func(c action.Context) error {
		a.editDeleteChar(c.EffectiveCount())
		a.enterInsert(false)
		return nil
	}, repeatable)
	reg("edit.delete_to_end", "delete to the end of the line", func(action.Context) error {
		a.editToEnd(false)
		return nil
	}, repeatable)
	reg("edit.change_to_end", "change to the end of the line", func(action.Context) error {
		a.editToEnd(true)
		return nil
	}, repeatable)
	reg("edit.put_after", "paste after", func(c action.Context) error {
		a.editPut(c.Register, true)
		return nil
	}, repeatable)
	reg("edit.put_before", "paste before", func(c action.Context) error {
		a.editPut(c.Register, false)
		return nil
	}, repeatable)
	reg("edit.undo", "undo", func(action.Context) error { a.undo(); return nil })
	reg("edit.redo", "redo", func(action.Context) error { a.redo(); return nil })
	reg("repeat.last", "repeat the last change", func(action.Context) error { return nil }, repeatable)

	// --- insert-mode editing ------------------------------------------------
	reg("insert.accept", "accept", func(action.Context) error { return a.insertAccept() })
	reg("insert.newline", "insert a line break", func(action.Context) error {
		if buf, _ := a.activeBuffer(); buf != nil {
			buf.Insert("\n")
		}
		return nil
	})
	reg("insert.backspace", "delete backwards", func(action.Context) error {
		a.insertBackspace()
		return nil
	})
	reg("insert.delete", "delete forwards", func(action.Context) error {
		a.editDeleteChar(1)
		return nil
	})
	reg("insert.delete_word_back", "delete a word backwards", func(action.Context) error {
		a.insertDeleteWord()
		return nil
	})
	reg("insert.delete_to_start", "delete to the start of the line", func(action.Context) error {
		a.insertDeleteToStart()
		return nil
	})
	reg("insert.put_register", "paste a register", func(c action.Context) error {
		if buf, _ := a.activeBuffer(); buf != nil {
			buf.Insert(a.engine.Registers().Get(c.Register).Text)
			a.afterEdit()
		}
		return nil
	})

	// --- visual mode --------------------------------------------------------
	reg("visual.yank", "yank the selection", func(action.Context) error {
		a.yankSelectedMessage()
		a.engine.SetMode(vim.Normal)
		return nil
	})
	reg("visual.delete", "delete the selection", func(action.Context) error {
		a.setStatus("deleting messages arrives with the rich-message sub-project; use :revoke")
		a.engine.SetMode(vim.Normal)
		return nil
	})
	reg("visual.change", "change the selection", func(action.Context) error {
		a.engine.SetMode(vim.Normal)
		return nil
	})
	reg("visual.lower", "lower case", func(action.Context) error {
		a.engine.SetMode(vim.Normal)
		return nil
	})
	reg("visual.upper", "upper case", func(action.Context) error {
		a.engine.SetMode(vim.Normal)
		return nil
	})
	reg("visual.other_end", "swap ends of the selection", func(action.Context) error { return nil })

	// --- command line -------------------------------------------------------
	reg("cmdline.accept", "run the command", func(action.Context) error { return a.runCmdLine() })
	reg("cmdline.cancel", "cancel", func(action.Context) error {
		a.cmdline = ""
		a.completions = nil
		a.editTarget = TargetNone
		a.engine.SetMode(vim.Normal)
		return nil
	})
	reg("cmdline.complete", "complete", func(action.Context) error { a.complete(1); return nil })
	reg("cmdline.complete_back", "complete backwards", func(action.Context) error {
		a.complete(-1)
		return nil
	})
	reg("cmdline.history_prev", "previous command", func(action.Context) error {
		if s, ok := a.cmdHistory.Prev(); ok {
			a.cmdline = s
		}
		return nil
	})
	reg("cmdline.history_next", "next command", func(action.Context) error {
		if s, ok := a.cmdHistory.Next(); ok {
			a.cmdline = s
		}
		return nil
	})
	reg("cmdline.backspace", "delete a character", func(action.Context) error {
		if a.cmdline == "" {
			a.editTarget = TargetNone
			a.engine.SetMode(vim.Normal)
			return nil
		}
		r := []rune(a.cmdline)
		a.cmdline = string(r[:len(r)-1])
		a.completions = nil
		return nil
	})
	reg("cmdline.delete_word_back", "delete a word", func(action.Context) error {
		a.cmdline = deleteWordBack(a.cmdline)
		return nil
	})
	reg("cmdline.clear", "clear the command line", func(action.Context) error {
		a.cmdline = ""
		return nil
	})

	// --- chat actions -------------------------------------------------------
	reg("chat.archive_toggle", "archive or unarchive", func(action.Context) error {
		return a.toggleChat("archive")
	})
	reg("chat.pin_toggle", "pin or unpin", func(action.Context) error {
		return a.toggleChat("pin")
	})
	reg("chat.mute_toggle", "mute or unmute", func(action.Context) error {
		return a.toggleChat("mute")
	})
	reg("chat.read_toggle", "mark read or unread", func(action.Context) error {
		return a.toggleChat("read")
	})

	// --- list ---------------------------------------------------------------
	reg("list.filter_cycle", "next filter", func(action.Context) error {
		a.list.CycleFilter()
		a.setStatus("filter: " + a.list.Filter())
		return nil
	})

	// --- quickfix -----------------------------------------------------------
	reg("qf.toggle", "toggle the quickfix window", func(action.Context) error {
		a.showQF = !a.showQF
		a.qf.SetOpen(a.showQF)
		return nil
	})
	reg("qf.open", "open the quickfix window", func(action.Context) error {
		a.showQF = true
		a.qf.SetOpen(true)
		return nil
	})
	reg("qf.next", "next result", func(action.Context) error { return a.qfMove(true) })
	reg("qf.prev", "previous result", func(action.Context) error { return a.qfMove(false) })
	reg("qf.picker", "results in the picker", func(action.Context) error {
		a.openQuickfixPicker()
		return nil
	})

	// --- pickers ------------------------------------------------------------
	reg("picker.chats", "find a chat", func(action.Context) error { a.openChatPicker(); return nil })
	reg("picker.actions", "list actions", func(action.Context) error { a.openActionPicker(); return nil })
	reg("picker.keys", "list keys", func(action.Context) error { a.openKeyPicker(); return nil })

	// --- marks and jumps ----------------------------------------------------
	reg("mark.set", "set a mark", func(c action.Context) error {
		if c.Arg == 0 {
			return nil
		}
		id := ""
		if m, ok := a.pane.Selected(); ok {
			id = m.ID
		}
		a.marks[c.Arg] = Jump{Chat: a.pane.Chat().JID, MessageID: id}
		a.setStatus(fmt.Sprintf("mark %c set", c.Arg))
		return nil
	})
	jumpToMark := func(c action.Context) error {
		j, ok := a.marks[c.Arg]
		if !ok {
			return fmt.Errorf("mark %c is not set", c.Arg)
		}
		a.jumpTo(j)
		return nil
	}
	reg("mark.jump", "jump to a mark", jumpToMark)
	reg("mark.jump_exact", "jump to a mark", jumpToMark)

	reg("jump.back", "jump back", func(action.Context) error {
		j, ok := a.jumps.Back()
		if !ok {
			a.setStatus("no earlier position")
			return nil
		}
		a.jumpTo(j)
		return nil
	})
	reg("jump.forward", "jump forward", func(action.Context) error {
		j, ok := a.jumps.Forward()
		if !ok {
			a.setStatus("no later position")
			return nil
		}
		a.jumpTo(j)
		return nil
	})

	// --- macros -------------------------------------------------------------
	// The engine owns recording and replay; these exist so the keys validate.
	reg("macro.record", "record a macro", func(action.Context) error { return nil })
	reg("macro.play", "play a macro", func(action.Context) error { return nil })

	// --- messages -----------------------------------------------------------
	reg("msg.reply", "reply to the selected message", func(action.Context) error {
		m, ok := a.pane.Selected()
		if !ok {
			return fmt.Errorf("no message is selected")
		}
		return a.startReply(m)
	})
	reg("msg.copy", "copy the selected message", func(action.Context) error {
		m, ok := a.pane.Selected()
		if !ok {
			return fmt.Errorf("no message is selected")
		}
		return a.copyText(m.Body())
	})
	reg("msg.react", "react to the selected message", func(action.Context) error {
		m, ok := a.pane.Selected()
		if !ok {
			return fmt.Errorf("no message is selected")
		}
		return a.promptReaction(m)
	})
	reg("msg.forward", "forward the selected message", func(action.Context) error {
		m, ok := a.pane.Selected()
		if !ok {
			return fmt.Errorf("no message is selected")
		}
		a.forwardPicker(m)
		return nil
	})
	reg("msg.download", "download the selected message's media", func(action.Context) error {
		m, ok := a.pane.Selected()
		if !ok || !m.HasMedia() {
			return fmt.Errorf("the selected message has no media")
		}
		return a.downloadMedia(m)
	})
	reg("msg.open", "open or play the media, or follow the link", func(action.Context) error {
		m, ok := a.pane.Selected()
		if !ok {
			return fmt.Errorf("no message is selected")
		}
		if m.HasMedia() {
			return a.openMedia(m)
		}
		if link := firstLink(m.Body()); link != "" {
			return a.openExternally(link)
		}
		return fmt.Errorf("nothing to open in this message")
	})
	reg("media.download_chat", "download every attachment in this chat",
		func(action.Context) error { return a.downloadAllInChat() })
	reg("media.summary", "what media this chat holds", func(action.Context) error {
		a.overlay.Open("media in this chat", a.mediaSummary())
		return nil
	})
	reg("media.toggle_preview", "show or hide inline previews", func(action.Context) error {
		next := a.cfg
		next.Media.Preview = !next.Media.Preview
		if err := a.applyConfig(next); err != nil {
			return err
		}
		a.pane.Invalidate()
		a.setStatus(label(next.Media.Preview, "previews on", "previews off"))
		return nil
	})
	reg("msg.delete", "delete the selected message for you", func(action.Context) error {
		m, ok := a.pane.Selected()
		if !ok {
			return fmt.Errorf("no message is selected")
		}
		return a.deleteMessage(m, false)
	})
	reg("msg.info", "show the selected message's details", func(action.Context) error {
		m, ok := a.pane.Selected()
		if !ok {
			return fmt.Errorf("no message is selected")
		}
		return a.showMessageInfo(m)
	})

	reg("msg.attach", "attach a file to the next message", func(action.Context) error {
		a.startCommand("attach ")
		return nil
	})
	reg("msg.paste", "paste the clipboard: a picture attaches, text types", func(action.Context) error {
		return a.pasteFromClipboard()
	})
	reg("msg.detach", "remove the last attachment", func(action.Context) error {
		return a.cmdDetach()
	})

	// --- chats --------------------------------------------------------------
	reg("chat.info", "show the selected chat's details", func(action.Context) error {
		c, ok := a.targetChat()
		if !ok {
			return fmt.Errorf("no chat is selected")
		}
		return a.showChatInfo(c)
	})
	reg("chat.delete", "remove the chat from the local store", func(action.Context) error {
		c, ok := a.targetChat()
		if !ok {
			return fmt.Errorf("no chat is selected")
		}
		return a.deleteChat(c)
	})

	// --- the context menu ---------------------------------------------------
	reg("menu.open", "open the context menu for whatever has focus",
		func(action.Context) error { a.openMenuAtCursor(); return nil })

	// --- application --------------------------------------------------------
	reg("app.quit", "quit", func(action.Context) error {
		a.quitting = true
		return nil
	})
	reg("app.lock", "lock", func(action.Context) error {
		if a.lockScreen == nil || !a.lockScreen.Lock() {
			return fmt.Errorf("no password is set (run: wa lock set)")
		}
		return nil
	})
	reg("app.reload", "reload the config", func(action.Context) error { a.reload(); return nil })
	reg("app.help", "show the keys", func(action.Context) error {
		a.openHelp()
		return nil
	})
	reg("app.log", "show the log", func(action.Context) error {
		a.openLog()
		return nil
	})
}

// --- helpers the actions call ----------------------------------------------

// togglePane swaps the conversation and the input box - the pair you move
// between constantly while reading and replying.
//
// From the chat list it steps into the conversation rather than jumping
// straight to the input, so Tab always means "further right" and never skips
// the thing you were about to read.
func (a *App) togglePane() {
	switch a.focus {
	case FocusList:
		a.setFocus(FocusChat)
	case FocusChat:
		a.setFocus(FocusComposer)
	default:
		a.setFocus(FocusChat)
	}
}

// cyclePane walks all three sections, which is what Shift-Tab is for.
func (a *App) cyclePane(dir int) {
	order := []Focus{FocusList, FocusChat, FocusComposer}
	at := 0
	for i, f := range order {
		if f == a.focus {
			at = i
		}
	}
	a.setFocus(order[((at+dir)%len(order)+len(order))%len(order)])
}

// setFocus moves the keyboard and points the editing target at whatever text
// buffer that section owns, so vim motions work on the draft and on the search
// box without a separate mode.
func (a *App) setFocus(f Focus) {
	a.focus = f
	switch f {
	case FocusComposer:
		a.editTarget = TargetComposer
	case FocusList:
		if a.editTarget == TargetComposer {
			a.editTarget = TargetNone
		}
	default:
		a.editTarget = TargetNone
	}
}

func (a *App) focusLeft() { a.setFocus(FocusList) }

func (a *App) focusRight() {
	if a.focus == FocusList {
		a.setFocus(FocusChat)
		return
	}
	a.setFocus(FocusComposer)
}

// enterInsert opens the right buffer for the pane that has focus: the search
// box on the left, the composer on the right.
func (a *App) enterInsert(after bool) {
	switch a.focus {
	case FocusList:
		a.editTarget = TargetSearch
	default:
		a.setFocus(FocusComposer)
	}
	if after {
		if buf, _ := a.activeBuffer(); buf != nil {
			cur := buf.Cursor()
			if cur.Col < buf.LineLen(cur.Line) {
				buf.SetCursor(vim.Pos{Line: cur.Line, Col: cur.Col + 1})
			}
		}
	}
	if _, undo := a.activeBuffer(); undo != nil {
		undo.Checkpoint()
	}
	a.engine.SetMode(vim.Insert)
}

// leaveInsert steps back one level: insert to normal-in-the-buffer, then out
// of the buffer entirely. That is what makes Esc twice return to the pane
// while Esc once leaves the draft editable with vim motions.
func (a *App) leaveInsert() {
	if a.engine.Mode() == vim.Insert {
		a.engine.SetMode(vim.Normal)
		return
	}
	switch a.editTarget {
	case TargetComposer:
		a.setFocus(FocusChat)
	case TargetSearch:
		a.editTarget = TargetNone
		a.setFocus(FocusList)
	}
	a.engine.SetMode(vim.Normal)
}

func (a *App) editDeleteChar(count int) {
	buf, undo := a.activeBuffer()
	if buf == nil {
		return
	}
	undo.Checkpoint()
	for i := 0; i < count; i++ {
		cur := buf.Cursor()
		if cur.Col >= buf.LineLen(cur.Line) {
			break
		}
		buf.Delete(vim.Span{From: cur, To: cur, Kind: vim.Inclusive})
	}
	a.afterEdit()
}

func (a *App) editToEnd(change bool) {
	buf, undo := a.activeBuffer()
	if buf == nil {
		return
	}
	undo.Checkpoint()
	cur := buf.Cursor()
	end := buf.LineLen(cur.Line)
	if end > cur.Col {
		buf.Delete(vim.Span{
			From: cur,
			To:   vim.Pos{Line: cur.Line, Col: end - 1},
			Kind: vim.Inclusive,
		})
	}
	a.afterEdit()
	if change {
		a.engine.SetMode(vim.Insert)
	}
}

func (a *App) editPut(register rune, after bool) {
	buf, undo := a.activeBuffer()
	if buf == nil {
		return
	}
	undo.Checkpoint()
	vim.Put(buf, a.engine.Registers().Get(register), after)
	a.afterEdit()
}

func (a *App) insertBackspace() {
	switch a.editTarget {
	case TargetCmdLine:
		if r := []rune(a.cmdline); len(r) > 0 {
			a.cmdline = string(r[:len(r)-1])
		}
		return
	case TargetFind:
		a.findBackspace()
		return
	}
	buf, _ := a.activeBuffer()
	if buf == nil {
		return
	}
	cur := buf.Cursor()
	if cur.Col == 0 && cur.Line == 0 {
		return
	}
	if cur.Col == 0 {
		prev := vim.Pos{Line: cur.Line - 1, Col: buf.LineLen(cur.Line - 1)}
		buf.Delete(vim.Span{From: prev, To: prev, Kind: vim.Inclusive})
	} else {
		at := vim.Pos{Line: cur.Line, Col: cur.Col - 1}
		buf.Delete(vim.Span{From: at, To: at, Kind: vim.Inclusive})
	}
	a.afterEdit()
}

func (a *App) insertDeleteWord() {
	if a.editTarget == TargetCmdLine {
		a.cmdline = deleteWordBack(a.cmdline)
		return
	}
	if a.editTarget == TargetFind {
		a.findLine = deleteWordBack(a.findLine)
		return
	}
	buf, undo := a.activeBuffer()
	if buf == nil {
		return
	}
	undo.Checkpoint()
	from := buf.Cursor()
	m := vim.Move(buf, "word_prev", 1, 0)
	if !m.Valid {
		return
	}
	buf.Delete(vim.Span{From: m.To, To: from, Kind: vim.Exclusive})
	a.afterEdit()
}

func (a *App) insertDeleteToStart() {
	if a.editTarget == TargetCmdLine {
		a.cmdline = ""
		return
	}
	if a.editTarget == TargetFind {
		a.findLine = ""
		return
	}
	buf, undo := a.activeBuffer()
	if buf == nil {
		return
	}
	undo.Checkpoint()
	cur := buf.Cursor()
	if cur.Col > 0 {
		buf.Delete(vim.Span{
			From: vim.Pos{Line: cur.Line},
			To:   cur,
			Kind: vim.Exclusive,
		})
	}
	a.afterEdit()
}

// insertAccept is Enter in insert mode: send, or apply the list search.
func (a *App) insertAccept() error {
	switch a.editTarget {
	case TargetSearch:
		a.list.SetSearch(a.searchBuf.Text())
		a.editTarget = TargetNone
		a.engine.SetMode(vim.Normal)
		return nil
	case TargetComposer:
		return a.send()
	}
	a.engine.SetMode(vim.Normal)
	return nil
}

// send posts the draft.
func (a *App) send() error {
	if a.composer.Empty() {
		return nil
	}
	chat := a.pane.Chat()
	if chat.JID.IsZero() {
		return fmt.Errorf("no chat is open")
	}
	if a.deps.Client == nil {
		return fmt.Errorf("no wacli client")
	}

	// Files first, because the caption belongs to the first of them and the
	// draft is about to be emptied.
	files := a.composer.Attachments()
	a.composer.ClearAttachments()

	text := a.composer.Take()

	label := text
	if len(files) > 0 {
		label = attachmentLabel(files, text)
	}
	local := a.pane.AddOptimistic(label)

	// A pending reply quotes the message and is then cleared, so the next
	// message is not silently attached to the same one.
	reply := a.replyTo
	a.replyTo = domain.Message{}

	client := a.deps.Client
	timeout := a.cfg.Wacli.Timeout.D()
	if timeout <= 0 {
		timeout = 30 * time.Second
	}

	// wacli refuses to message the linked account unless told explicitly,
	// because sending to yourself is usually a mistake. Here it is not: the
	// "Message yourself" chat is a real chat that the phone app shows at the
	// top of the list, and refusing to send in the chat that is open would be
	// the surprising behaviour.
	self := a.isSelfChat(chat.JID)

	daemonRef := a.deps.Daemon
	socketWait := a.cfg.Sync.SendSocketWait.D()

	a.queue(func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), timeout)
		defer cancel()

		// A lock handover - pinning a chat, forwarding a message - takes the
		// delegation socket away for a few seconds. Waiting for it back beats
		// throwing the message away.
		if err := daemonRef.WaitSendReady(ctx, socketWait); err != nil {
			return sendFailMsg{localID: local.ID, text: text, err: err}
		}

		// An attachment goes as a file, with the draft as its caption. Several
		// go one after another, and only the first carries the caption -
		// repeating it under every picture is not what anybody means.
		if len(files) > 0 {
			return sendFiles(ctx, client, sendFilesArgs{
				local: local.ID, to: chat.JID, files: files,
				caption: text, reply: reply,
			})
		}

		req := wacli.SendTextRequest{To: chat.JID, Message: text, AllowSelf: self}
		if reply.ID != "" {
			req.ReplyTo = reply.ID
			req.ReplyToSender = reply.SenderJID
		}
		sent, err := client.SendText(ctx, req)

		// Not every stored message can be quoted - wacli says so plainly for
		// the ones it cannot rebuild. Losing the whole message over a lost
		// quote is the wrong trade: send it anyway and say the quote was
		// dropped.
		if err != nil && req.ReplyTo != "" && strings.Contains(err.Error(), "cannot quote") {
			plain := wacli.SendTextRequest{To: chat.JID, Message: text, AllowSelf: self}
			if sent, err2 := client.SendText(ctx, plain); err2 == nil {
				return sentMsg{
					localID: local.ID, realID: sent.ID,
					note: "sent without the quote: that message cannot be replied to",
				}
			}
		}
		if err != nil {
			return sendFailMsg{localID: local.ID, text: text, err: err}
		}
		return sentMsg{localID: local.ID, realID: sent.ID, quote: quoteOf(reply)}
	})
	return nil
}

// yankSelectedMessage copies the message under the cursor.
func (a *App) yankSelectedMessage() {
	m, ok := a.pane.Selected()
	if !ok {
		return
	}
	a.engine.Registers().Yank('"', m.Body(), false)
	a.setStatus("yanked")
}

// toggleChat flips a chat flag and records how to undo it.
func (a *App) toggleChat(what string) error {
	c, ok := a.targetChat()
	if !ok {
		return fmt.Errorf("no chat is selected")
	}
	if a.deps.Client == nil {
		return fmt.Errorf("no wacli client")
	}
	client := a.deps.Client
	jid := c.JID

	// None of these are delegated to a running sync, so each one needs the
	// store lock handed over. That is why they did nothing before: wacli
	// answered "store is locked" and the status line flashed past.
	var (
		act     func(context.Context) error
		inverse func(context.Context) error
		doing   string
		label   string
	)
	switch what {
	case "archive":
		on := !c.Archived
		act = func(ctx context.Context) error { return client.Archive(ctx, jid, on) }
		inverse = func(ctx context.Context) error { return client.Archive(ctx, jid, !on) }
		doing = map[bool]string{true: "archiving", false: "unarchiving"}[on]
		label = map[bool]string{true: "archived", false: "unarchived"}[on]
	case "pin":
		on := !c.Pinned
		act = func(ctx context.Context) error { return client.Pin(ctx, jid, on) }
		inverse = func(ctx context.Context) error { return client.Pin(ctx, jid, !on) }
		doing = map[bool]string{true: "pinning", false: "unpinning"}[on]
		label = map[bool]string{true: "pinned", false: "unpinned"}[on]
	case "mute":
		on := !c.Muted(time.Now())
		act = func(ctx context.Context) error { return client.Mute(ctx, jid, on) }
		inverse = func(ctx context.Context) error { return client.Mute(ctx, jid, !on) }
		doing = map[bool]string{true: "muting", false: "unmuting"}[on]
		label = map[bool]string{true: "muted", false: "unmuted"}[on]
	case "read":
		on := c.Unread || c.UnreadCount > 0
		if on {
			act = func(ctx context.Context) error { return client.MarkRead(ctx, jid) }
			inverse = func(ctx context.Context) error { return client.MarkUnread(ctx, jid) }
			doing, label = "marking read", "marked read"
		} else {
			act = func(ctx context.Context) error { return client.MarkUnread(ctx, jid) }
			inverse = func(ctx context.Context) error { return client.MarkRead(ctx, jid) }
			doing, label = "marking unread", "marked unread"
		}
	}
	// The inverse needs the lock too, so wrap it before it reaches the ring.
	gated := inverse
	a.pushUndo(label, func(context.Context) error {
		return a.locked("undoing "+label, "undone", gated,
			func() error { return a.refreshChat(jid) })
	})

	return a.locked(doing, label, act, func() error { return a.refreshChat(jid) })
}

// refreshChat re-reads one row of the chat list after something changed it.
func (a *App) refreshChat(jid domain.JID) error {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	return a.list.Invalidate(ctx, jid)
}

// pushUndo adds a reversible action to the ring.
func (a *App) pushUndo(what string, inverse func(context.Context) error) {
	a.undoRing = append(a.undoRing, reversible{what: what, inverse: inverse})
	if len(a.undoRing) > 50 {
		a.undoRing = a.undoRing[len(a.undoRing)-50:]
	}
}

// undo reverses the last reversible action, or steps back in the draft when a
// text buffer has focus.
//
// Sends and deletions are deliberately absent from the ring. An undo key that
// sometimes retracts a message already delivered to another person is a trap,
// so it never does: retraction stays an explicit, typed command.
func (a *App) undo() {
	if buf, undo := a.activeBuffer(); buf != nil {
		if !undo.Undo() {
			a.setStatus("nothing to undo")
		}
		a.afterEdit()
		return
	}
	if len(a.undoRing) == 0 {
		a.setStatus("nothing to undo (sends are not undoable; use :revoke)")
		return
	}
	last := a.undoRing[len(a.undoRing)-1]
	a.undoRing = a.undoRing[:len(a.undoRing)-1]

	ctx, cancel := context.WithTimeout(context.Background(), a.cfg.Wacli.Timeout.D())
	defer cancel()
	if err := last.inverse(ctx); err != nil {
		a.setError(fmt.Sprintf("undo %s: %v", last.what, err))
		return
	}
	a.setStatus("undid " + last.what)
	if c, ok := a.list.Selected(); ok {
		_ = a.list.Invalidate(ctx, c.JID)
	}
}

func (a *App) redo() {
	if buf, undo := a.activeBuffer(); buf != nil {
		if !undo.Redo() {
			a.setStatus("nothing to redo")
		}
		a.afterEdit()
		return
	}
	a.setStatus("redo applies to a draft, not to actions")
}

// --- the / prompt -----------------------------------------------------------

func (a *App) startFind(forward bool) {
	a.findLine = ""
	a.findForward = forward
	a.editTarget = TargetFind
	a.engine.SetMode(vim.Search)
}

func (a *App) acceptFind() {
	pattern := a.findLine
	a.findHistory.Add(pattern)
	a.findLine = ""
	a.editTarget = TargetNone
	a.engine.SetMode(vim.Normal)

	if pattern == "" {
		return
	}
	if !a.pane.Search(pattern, a.findForward, a.cfg.UI.IgnoreCase, a.cfg.UI.SmartCase) {
		a.setError(fmt.Sprintf("pattern not found: %s", pattern))
		return
	}
	a.setStatus(fmt.Sprintf("%d matches", a.pane.MatchCount()))
}

func (a *App) cancelFind() {
	a.findLine = ""
	a.editTarget = TargetNone
	a.engine.SetMode(vim.Normal)
}

func (a *App) findBackspace() {
	if a.findLine == "" {
		a.cancelFind()
		return
	}
	r := []rune(a.findLine)
	a.findLine = string(r[:len(r)-1])
}

// deleteWordBack removes the last whitespace-delimited word.
func deleteWordBack(s string) string {
	i := len(s)
	for i > 0 && s[i-1] == ' ' {
		i--
	}
	for i > 0 && s[i-1] != ' ' {
		i--
	}
	return s[:i]
}

// --- quickfix ---------------------------------------------------------------

func (a *App) qfMove(forward bool) error {
	var (
		it QFItem
		ok bool
	)
	if forward {
		it, ok = a.qf.Next()
	} else {
		it, ok = a.qf.Prev()
	}
	if !ok {
		if cur, has := a.qf.Current(); has && a.qf.Len() > 0 {
			it, ok = cur, true
		} else {
			a.setStatus("no more results")
			return nil
		}
	}
	return a.openQuickfixItem(it)
}

func (a *App) openQuickfixItem(it QFItem) error {
	if err := a.openChat(it.Chat); err != nil {
		return err
	}
	for i, m := range a.pane.Messages() {
		if m.ID == it.MessageID {
			a.pane.Move(i - a.pane.Index())
			return nil
		}
	}
	// The result is older than the loaded window; say so rather than leaving
	// the cursor somewhere arbitrary.
	a.setStatus("result is further back in this chat; scroll up to load it")
	return nil
}

// --- pickers ----------------------------------------------------------------

func (a *App) openChatPicker() {
	items := make([]PickerItem, 0, a.list.Len())
	for _, c := range a.list.Rows() {
		items = append(items, PickerItem{
			Label:  c.DisplayName(),
			Detail: c.LastSnippet,
			Value:  c.JID.String(),
		})
	}
	a.picker.Open("chats", items, func(it PickerItem) error {
		j, err := domain.ParseJID(it.Value)
		if err != nil {
			return err
		}
		return a.openChat(j)
	})
}

func (a *App) openActionPicker() {
	names := a.reg.Names()
	items := make([]PickerItem, 0, len(names))
	for _, n := range names {
		act, _ := a.reg.Lookup(n)
		items = append(items, PickerItem{Label: n, Detail: act.Summary, Value: n})
	}
	a.picker.Open("actions", items, func(it PickerItem) error {
		return a.reg.Run(it.Value, action.Context{})
	})
}

func (a *App) openKeyPicker() {
	var items []PickerItem
	for _, mode := range a.keymap.Modes() {
		for notation, target := range a.keymap.Bindings(mode) {
			items = append(items, PickerItem{
				Label:  fmt.Sprintf("%-10s %s", mode.String(), notation),
				Detail: target.Name,
				Value:  target.Name,
			})
		}
	}
	SortItems(items)
	a.picker.Open("keys", items, func(PickerItem) error { return nil })
}

func (a *App) openQuickfixPicker() {
	items := make([]PickerItem, 0, a.qf.Len())
	for i, it := range a.qf.Items() {
		items = append(items, PickerItem{
			Label:  it.ChatName,
			Detail: it.Text,
			Value:  fmt.Sprintf("%d", i),
		})
	}
	a.picker.Open("results", items, func(it PickerItem) error {
		var i int
		fmt.Sscanf(it.Value, "%d", &i)
		got, ok := a.qf.Select(i)
		if !ok {
			return nil
		}
		return a.openQuickfixItem(got)
	})
}

// isSelfChat reports whether a JID is the linked account's own chat.
//
// The device suffix is ignored: the store may hold "…@s.whatsapp.net" while
// the account is "…:12@s.whatsapp.net", and they are the same person.
func (a *App) isSelfChat(j domain.JID) bool {
	return !a.deps.Self.IsZero() && j.User == a.deps.Self.User
}

// quoteOf is what to remember about a reply's target.
//
// The text is kept alongside the id because the quote bar shows it, and the
// message being quoted may have scrolled out of the page by the time the reply
// is drawn again.
func quoteOf(m domain.Message) store.Quote {
	if m.ID == "" {
		return store.Quote{}
	}
	return store.Quote{
		QuotedID:     m.ID,
		QuotedSender: m.SenderJID.String(),
		QuotedText:   m.Body(),
	}
}

// refreshPane re-reads the open conversation.
func (a *App) refreshPane() error {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	return a.pane.Refresh(ctx)
}

// targetChat is the chat a chat-level action applies to.
//
// It is the open conversation whenever the keyboard is on the right, and the
// list cursor only when the list itself has focus. Those are usually the same
// chat and occasionally are not: moving the list cursor without pressing enter
// leaves the two apart, and pinning what you are reading is what "pin" means
// while you are reading it - not pinning whatever the cursor drifted onto.
func (a *App) targetChat() (domain.Chat, bool) {
	if a.focus != FocusList {
		if c := a.pane.Chat(); !c.JID.IsZero() {
			return c, true
		}
	}
	return a.list.Selected()
}

// sendFilesArgs is what one attachment send needs.
type sendFilesArgs struct {
	local   string
	to      domain.JID
	files   []string
	caption string
	reply   domain.Message
}

// sendFiles sends each attached file, the first carrying the caption.
func sendFiles(ctx context.Context, c *wacli.Client, a sendFilesArgs) tea.Msg {
	var last wacli.SentMessage
	for i, f := range a.files {
		req := wacli.SendFileRequest{To: a.to, Path: f}
		if i == 0 {
			req.Caption = a.caption
			req.ReplyTo = a.reply.ID
			req.ReplyToSender = a.reply.SenderJID
		}
		sent, err := c.SendFile(ctx, req)
		if err != nil {
			return sendFailMsg{
				localID: a.local,
				text:    a.caption,
				err:     fmt.Errorf("%s: %w", filepath.Base(f), err),
			}
		}
		last = sent
	}
	note := ""
	if len(a.files) > 1 {
		note = fmt.Sprintf("sent %d files", len(a.files))
	}
	return sentMsg{
		localID: a.local, realID: last.ID,
		note: note, quote: quoteOf(a.reply),
	}
}

// attachmentLabel is what the bubble says while an attachment is on its way.
func attachmentLabel(files []string, caption string) string {
	names := make([]string, 0, len(files))
	for _, f := range files {
		names = append(names, filepath.Base(f))
	}
	label := "📎 " + strings.Join(names, ", ")
	if caption != "" {
		label += "\n" + caption
	}
	return label
}

// startCommand opens the : prompt with a verb already typed.
//
// Used by the bindings that are really shortcuts for a command: attaching a
// file needs a path, and the prompt with its completion is the right place to
// type one.
func (a *App) startCommand(prefix string) {
	a.cmdline = prefix
	a.completions = nil
	a.editTarget = TargetCmdLine
	a.engine.SetMode(vim.CmdLine)
}
