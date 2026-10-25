"""Modal dialogs: the action picker, text entry, confirmations, setup."""

import re
import threading

from rich.table import Table
from rich.text import Text
from textual import on, work
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from . import devices, hotkeys, identify, permissions


class Dialog(ModalScreen):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def action_cancel(self):
        self.dismiss(None)


class ConfirmDialog(Dialog):
    def __init__(self, title, message, confirm="Continue"):
        super().__init__()
        self.title_text, self.message, self.confirm = title, message, confirm

    def compose(self):
        with Vertical(classes="dialog") as box:
            box.border_title = f" {self.title_text.upper()} "
            yield Static(self.message, classes="dialog-body")
            with Horizontal(classes="dialog-buttons"):
                yield Button(self.confirm, variant="primary", id="yes")
                yield Button("Cancel", id="no")

    def on_mount(self):
        self.query_one("#yes").focus()

    @on(Button.Pressed)
    def pressed(self, event):
        self.dismiss(event.button.id == "yes")


class TextDialog(Dialog):
    """One-line input with live validation and a preview of what will happen."""

    def __init__(self, title, body, placeholder, value, validate):
        super().__init__()
        self.title_text, self.body, self.placeholder, self.value, self.validate = title, body, placeholder, value, validate
        self.result = None

    def compose(self):
        with Vertical(classes="dialog") as box:
            box.border_title = f" {self.title_text.upper()} "
            yield Static(self.body, classes="dialog-body")
            yield Input(value=self.value, placeholder=self.placeholder, id="text")
            yield Static("", id="preview", classes="dialog-preview")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Save", variant="primary", id="save", disabled=True)
                yield Button("Cancel", id="cancel")

    def on_mount(self):
        self.query_one("#text").focus()
        self.check(self.value)

    def check(self, text):
        self.result, message = self.validate(text)
        preview = self.query_one("#preview", Static)
        preview.update(message)
        preview.set_class(self.result is None and bool(text.strip()), "error")
        self.query_one("#save", Button).disabled = self.result is None

    @on(Input.Changed)
    def changed(self, event):
        self.check(event.value)

    @on(Input.Submitted)
    @on(Button.Pressed, "#save")
    def save(self):
        if self.result is not None:
            self.dismiss(self.result)

    @on(Button.Pressed, "#cancel")
    def cancel(self):
        self.dismiss(None)


class IdentifyDialog(Dialog):
    """Waits for a press of any button on the mouse."""

    def __init__(self, mouse):
        super().__init__()
        self.mouse = mouse
        self.cancelled = threading.Event()

    def compose(self):
        with Vertical(classes="dialog narrow") as box:
            box.border_title = " DETECT BUTTON "
            yield Label("Press the mouse button you want to change", classes="dialog-title")
            yield Static(
                "The mouse is paused while you do this, so the press won't do anything else.\n"
                "Press Esc to cancel.",
                classes="dialog-body",
            )

    def on_mount(self):
        self.listen()

    @work(thread=True)
    def listen(self):
        code = identify.wait_for_button(self.mouse, self.cancelled)
        if not self.cancelled.is_set():
            self.app.call_from_thread(self.dismiss, code if code is not None else -1)

    def action_cancel(self):
        self.cancelled.set()
        self.dismiss(None)


class PermissionDialog(Dialog):
    def __init__(self, mouse):
        super().__init__()
        self.mouse = mouse

    def compose(self):
        with Vertical(classes="dialog") as box:
            box.border_title = " ONE-TIME SETUP "
            yield Static(
                f"To change settings stored inside your [b]{self.mouse.name}[/b] (buttons, lighting, "
                "sensitivity) and to recognise which button you press, omarchy-hyprmouse needs permission "
                "to talk to your mouse.\n\n"
                "You'll be asked for your password once. After that it just works, even after "
                "restarts. Keyboards are not included.",
                classes="dialog-body",
            )
            yield Static("", id="status", classes="dialog-preview")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Allow", variant="primary", id="allow")
                yield Button("Not now", id="later")

    def on_mount(self):
        self.query_one("#allow").focus()

    @on(Button.Pressed, "#later")
    def later(self):
        self.dismiss(False)

    @on(Button.Pressed, "#allow")
    def allow(self):
        self.query_one("#status", Static).update("Waiting for your password…")
        self.query_one("#allow", Button).disabled = True
        self.install()

    @work(thread=True)
    def install(self):
        error = permissions.install(devices.sysfs_nodes(self.mouse))
        self.app.call_from_thread(self.finished, error)

    def finished(self, error):
        if error:
            self.query_one("#status", Static).update(f"[red]{error}[/red]")
            self.query_one("#allow", Button).disabled = False
        else:
            self.dismiss(True)


class ActionPicker(Dialog):
    """Searchable list of everything a button can do."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("down", "move('cursor_down')", show=False),
        Binding("up", "move('cursor_up')", show=False),
        Binding("pagedown", "move('page_down')", show=False),
        Binding("pageup", "move('page_up')", show=False),
    ]

    def __init__(self, button_name, default_name, current, all_hotkeys, media_keys=None, existing=None):
        super().__init__()
        self.button_name, self.default_name, self.current = button_name, default_name, current
        self.existing = existing or {}
        self.all_hotkeys, self.media_keys = all_hotkeys, media_keys or {}
        self.choices = {}

    def compose(self):
        with Vertical(classes="dialog wide") as box:
            box.border_title = f" ASSIGN · {self.button_name.upper()} "
            yield Label(f"What should [b $accent]{self.button_name}[/] do?", classes="dialog-title")
            yield Input(placeholder="Search… e.g. workspace, screenshot, volume, browser", id="search")
            yield OptionList(id="choices")
            yield Static("↑↓ move   Enter choose   Esc cancel", classes="dialog-hint")

    def on_mount(self):
        self.populate("")
        self.query_one("#search").focus()

    def sections(self):
        basics = [
            ("default", f"Default: {self.default_name}", "", {"kind": "default"}),
            ("disabled", "Do nothing", "turn the button off", {"kind": "disabled"}),
        ]
        suggested = [
            (f"hotkey:{h.keys}", h.description, h.combo,
             {"kind": "hotkey", "keys": h.keys, "label": h.description})
            for h in hotkeys.suggested(self.all_hotkeys)
        ]
        on_mouse = [
            (f"media:{usage}", f"{label} (stored in the mouse)", "works on any computer",
             {"kind": "media", "usage": usage})
            for usage, label in self.media_keys.items()
        ]
        everything = [
            (f"hotkey:{h.keys}", h.description, h.combo,
             {"kind": "hotkey", "keys": h.keys, "label": h.description})
            for h in self.all_hotkeys
        ]
        custom = [
            ("command", "Run a command…", "any program or script", {"kind": "command"}),
            ("shortcut", "Press a key combination…", "e.g. Ctrl + Shift + T", {"kind": "shortcut"}),
        ]
        return [
            ("Basics", basics),
            ("Suggested", suggested),
            ("Media keys built into the mouse", on_mouse),
            (f"All Omarchy shortcuts ({len(everything)})", everything),
            ("Custom", custom),
        ]

    def row(self, choice_id, title, detail):
        grid = Table.grid(expand=True, padding=(0, 1))
        grid.add_column(ratio=1, no_wrap=True)
        grid.add_column(justify="right", style="dim", no_wrap=True)
        marker = "● " if choice_id == self.current else "  "
        grid.add_row(Text(marker + title, style="bold" if marker.strip() else ""), detail)
        return grid

    def populate(self, query):
        tokens = query.lower().split()
        options, self.choices = [], {}
        sections = self.sections()
        nothing_found = tokens and not any(
            all(t in f"{item[1]} {item[2]} {section}".lower() for t in tokens)
            for section, items in sections for item in items
        )
        for index, (section, items) in enumerate(sections):
            # With no matches at all, still offer the custom actions.
            fallback = nothing_found and section == "Custom"
            matched = [
                item for item in items
                if fallback or all(t in f"{item[1]} {item[2]} {section}".lower() for t in tokens)
            ]
            if not matched:
                continue
            if options:
                options.append(None)
            options.append(Option(f"[b $accent]{section.upper()}[/]", disabled=True))
            for choice_id, title, detail, choice in matched:
                option_id = f"{index}|{choice_id}"
                self.choices[option_id] = choice
                options.append(Option(self.row(choice_id, title, detail), id=option_id))

        option_list = self.query_one("#choices", OptionList)
        option_list.clear_options()
        option_list.add_options(options)
        first = next((i for i, o in enumerate(option_list.options) if not o.disabled), None)
        if tokens or self.current is None:
            option_list.highlighted = first
        else:
            current = next(
                (i for i, o in enumerate(option_list.options)
                 if o.id and o.id.split("|", 1)[1] == self.current),
                first,
            )
            option_list.highlighted = current

    @on(Input.Changed, "#search")
    def search(self, event):
        self.populate(event.value)

    def action_move(self, action):
        getattr(self.query_one("#choices", OptionList), f"action_{action}")()

    @on(Input.Submitted, "#search")
    def submit(self):
        option_list = self.query_one("#choices", OptionList)
        if option_list.highlighted is not None:
            self.choose(option_list.get_option_at_index(option_list.highlighted).id)

    @on(OptionList.OptionSelected)
    def selected(self, event):
        self.choose(event.option.id)

    def choose(self, option_id):
        choice = self.choices.get(option_id)
        if choice is None:
            return
        if choice["kind"] == "command":
            self.app.push_screen(
                TextDialog(
                    f"{self.button_name} runs a command",
                    "Type a command, exactly as you would in a terminal. It runs in the background.\n"
                    "[dim]Examples: omarchy-launch-browser · nautilus · notify-send 'Hello'[/dim]",
                    "command to run",
                    self.current_value("command"),
                    validate_command,
                ),
                self.dismiss_with("command"),
            )
        elif choice["kind"] == "shortcut":
            self.app.push_screen(
                TextDialog(
                    f"{self.button_name} presses keys",
                    "Type the keys to press, joined with +. The focused window receives them.\n"
                    "[dim]Examples: Ctrl + C · Ctrl + Shift + T · Alt + Left · F5[/dim]",
                    "e.g. Ctrl + Shift + T",
                    self.current_value("shortcut"),
                    validate_shortcut,
                ),
                self.dismiss_with("shortcut"),
            )
        else:
            self.dismiss(choice)

    def dismiss_with(self, kind):
        field = "command" if kind == "command" else "keys"

        def done(value):
            if value:
                self.dismiss({"kind": kind, field: value})

        return done

    def current_value(self, kind):
        if self.existing.get("kind") != kind:
            return ""
        if kind == "shortcut":
            return hotkeys.pretty_combo(self.existing["keys"])
        return self.existing.get("command", "")


# ---------------------------------------------------------------------------
# Validation for the custom actions

MODIFIER_ALIASES = {"CONTROL": "CTRL", "WIN": "SUPER", "META": "SUPER", "CMD": "SUPER", "LOGO": "SUPER"}
NAMED_KEYS = {
    "enter": "Return", "return": "Return", "esc": "Escape", "escape": "Escape", "tab": "Tab",
    "space": "space", "backspace": "BackSpace", "delete": "Delete", "del": "Delete",
    "insert": "Insert", "ins": "Insert", "home": "Home", "end": "End",
    "pageup": "Page_Up", "page_up": "Page_Up", "pgup": "Page_Up",
    "pagedown": "Page_Down", "page_down": "Page_Down", "pgdn": "Page_Down",
    "left": "Left", "right": "Right", "up": "Up", "down": "Down", "print": "Print",
    "minus": "minus", "-": "minus", "equal": "equal", "=": "equal", "comma": "comma", ",": "comma",
    "period": "period", ".": "period", "slash": "slash", "/": "slash", "semicolon": "semicolon",
    ";": "semicolon", "apostrophe": "apostrophe", "'": "apostrophe", "grave": "grave", "`": "grave",
    "bracketleft": "bracketleft", "[": "bracketleft", "bracketright": "bracketright",
    "]": "bracketright", "backslash": "backslash", "\\": "backslash",
}


def validate_shortcut(text):
    parts = [p for p in re.split(r"\s*\+\s*|\s+", text.strip()) if p]
    if not parts:
        return None, "Type a key combination, like Ctrl + Shift + T"
    mods, key = [], None
    for part in parts:
        upper = MODIFIER_ALIASES.get(part.upper(), part.upper())
        if upper in hotkeys.MODIFIERS:
            if upper not in mods:
                mods.append(upper)
            continue
        if key is not None:
            return None, f"Use one main key only (got “{key}” and “{part}”)"
        if part.lower() in NAMED_KEYS:
            key = NAMED_KEYS[part.lower()]
        elif len(part) == 1 and part.isalnum():
            key = part.upper()
        elif re.fullmatch(r"[Ff]([1-9]|1[0-9]|2[0-4])", part):
            key = part.upper()
        else:
            return None, f"Unknown key “{part}”"
    if key is None:
        return None, "Add the main key after the modifiers, e.g. Ctrl + T"
    mods.sort(key=hotkeys.MODIFIERS.index)
    combo = "+".join(mods + [key])
    return combo, f"Will press: [b]{hotkeys.pretty_combo(combo)}[/b]"


def validate_command(text):
    command = text.strip()
    if not command:
        return None, "Type a command to run"
    return command, f"Will run: [b]{command}[/b]"
