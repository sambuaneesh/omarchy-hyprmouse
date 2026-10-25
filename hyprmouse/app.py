"""The omarchy-hyprmouse TUI: what mouse buttons do, plus lighting and sensitivity."""

import os

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Label,
    RadioSet,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from . import devices, drivers, hotkeys, hypr, integration
from .art import MouseArt
from .dialogs import ActionPicker, ConfirmDialog, IdentifyDialog, PermissionDialog
from .drivers import DriverError
from .store import Store
from .widgets import GREEN, THEME, Choice, Slider, big_number

# Errors a driver call can raise; the UI reports them instead of crashing.
DEVICE_ERRORS = (OSError, DriverError, NotImplementedError, KeyError)

CSS = """
Screen { background: $background; }
#topbar { height: 2; padding: 1 2 0 2; }
#title { width: auto; text-style: bold; color: $accent; }
#device { width: 1fr; text-align: right; color: $text-muted; text-style: bold; }
#rule { height: 1; margin: 0 2; color: $accent 40%; }
#mouse-select { width: 46; display: none; margin: 0 2; }
#banner { display: none; height: auto; margin: 1 2 0 2; padding: 0 1;
          border-left: thick $warning; background: $warning 10%; color: $text; }
#empty { display: none; height: 1fr; content-align: center middle; text-align: center; color: $text-muted; }

TabbedContent { height: 1fr; margin: 0 1; }
Tabs { height: 2; }
Tab { text-style: bold; color: $text-muted; padding: 0 2; }
Tab.-active { color: $accent; }
Tab:hover { color: $text; }
Underline > .underline--bar { background: $panel; color: $accent; }
TabPane { padding: 1 1 0 1; }
.page { height: 1fr; }
.art-column { width: 33; height: auto; }
.caption { width: 31; height: auto; padding: 0 0 0 1; }
.controls { width: 1fr; height: 1fr; padding: 0 0 0 2; border-left: solid $panel; }

#buttons { height: auto; max-height: 1fr; background: transparent; scrollbar-size-horizontal: 0; }
#buttons > .datatable--header, #buttons > .datatable--header-cursor {
    background: transparent; color: $text-muted; text-style: bold; }
#buttons > .datatable--cursor { background: $accent 22%; color: $text; text-style: bold; }
#buttons:blur > .datatable--cursor { background: $accent 10%; }
.hint { color: $text-muted; padding: 1 0 0 0; }
.keys { color: $text-muted; padding: 1 0 0 0; }

.section { color: $accent; text-style: bold; padding: 1 0 0 0; }
.section.first { padding: 0; }
.field { height: auto; padding: 1 0 0 0; }
.field-label { width: 14; color: $text-muted; }
RadioSet { layout: horizontal; border: none; background: transparent; padding: 0; height: auto; }
RadioSet:focus { border: none; background: transparent; background-tint: $foreground 0%; }
Choice { background: transparent; margin: 0 2 0 0; width: auto; padding: 0 1; border: none; }
RadioSet > Choice { width: auto; }
Choice > .toggle--button { color: #3a3a3a; background: transparent; }
Choice > .toggle--label { padding: 0 0 0 1; }
Choice.-on > .toggle--button { color: $accent; }
Choice.-on { color: $accent; text-style: bold; }
RadioSet:blur > Choice.-selected > .toggle--label { background: transparent; }
RadioSet:focus > Choice.-selected > .toggle--label { background: transparent; color: $text;
                                                     text-style: bold underline; }
RadioSet:focus > Choice.-selected.-on > .toggle--label { color: $accent; }
Choice:hover { background: $panel; }
.field Slider { margin: 0 2 0 0; }

#dpi-readout { height: 4; width: auto; padding: 1 0 0 0; }
.presets { height: auto; padding: 1 0 0 14; }
.presets Button { min-width: 8; margin: 0 1 0 0; height: 1; border: none; background: $panel;
                  color: $text-muted; text-style: bold; }
.presets Button.current { background: $accent; color: $background; }
.presets Button:hover, .presets Button:focus { background: $accent 35%; color: $text; }

.dialog { width: 72; max-width: 95%; height: auto; max-height: 90%; background: $surface;
          border: solid $accent; border-title-color: $accent; border-title-style: bold;
          padding: 1 2; }
.dialog.wide { width: 92; }
.dialog.narrow { width: 62; }
.dialog-title { text-style: bold; padding: 0 0 1 0; width: 100%; }
.dialog-body { padding: 0 0 1 0; color: $text; }
.dialog-preview { height: auto; padding: 1 0 0 0; color: $success; }
.dialog-preview.error { color: $error; }
.dialog-buttons { height: auto; padding: 1 0 0 0; align-horizontal: right; }
.dialog-buttons Button { margin: 0 0 0 1; border: none; height: 1; min-width: 12;
                         background: $panel; text-style: bold; }
.dialog-buttons Button.-primary { background: $accent; color: $background; }
.dialog-buttons Button:focus { text-style: bold reverse; }
.dialog-hint { color: $text-muted; padding: 1 0 0 0; }
Input { border: tall $panel; background: $background; }
Input:focus { border: tall $accent; }
#choices { height: auto; max-height: 22; border: none; background: transparent; margin: 1 0 0 0; }
#choices > .option-list--option-highlighted { background: $accent 25%; color: $text; text-style: bold; }
#choices > .option-list--separator { color: $panel; }
ModalScreen { align: center middle; background: $background 70%; }
Footer { background: $surface; }
Footer FooterKey .footer-key--key { color: $accent; background: $surface; }
Toast { border-left: thick $accent; background: $surface; }
Toast.-error { border-left: thick $error; }
Toast.-warning { border-left: thick $warning; }
"""


class HyprMouse(App):
    TITLE = "omarchy-hyprmouse"
    ENABLE_COMMAND_PALETTE = False
    CSS = CSS

    BINDINGS = [
        Binding("enter", "change", "Change", priority=False),
        Binding("p", "identify", "Pick by pressing"),
        Binding("d", "reset_button", "Default"),
        Binding("R", "reset_all", "Reset all"),
        Binding("a", "allow", "Allow access"),
        Binding("1", "tab('buttons-tab')", show=False),
        Binding("2", "tab('lighting-tab')", show=False),
        Binding("3", "tab('performance-tab')", show=False),
        Binding("q", "quit", "Quit"),
    ]

    BUTTON_ACTIONS = {"change", "identify", "reset_button", "reset_all"}

    def __init__(self):
        super().__init__()
        self.store = Store()
        self.hotkeys = []
        self.mice = []
        self.mouse = None
        self.driver = None
        self.onboard = {}  # Linux button code -> ButtonSetting stored in the mouse
        self.signature = None
        self.state = {}  # last value read from / written to the mouse, per control
        self.light = {}  # zone key -> [effect, brightness], mirrored on the drawing
        self.asked_permission = False
        self.pending = {}

    # Layout

    def compose(self) -> ComposeResult:
        with Horizontal(id="topbar"):
            yield Label("󰍽  HYPRMOUSE", id="title")
            yield Label("", id="device")
        yield Static("━" * 400, id="rule")
        yield Select([], id="mouse-select", allow_blank=True, prompt="Choose a mouse")
        yield Static("", id="banner")
        yield Static("[b]No mouse found[/b]\n\nPlug one in. This screen updates by itself.", id="empty")
        with TabbedContent(id="tabs"):
            with TabPane("CUSTOMIZE", id="buttons-tab"):
                with Horizontal(classes="page"):
                    with Vertical(classes="art-column"):
                        yield MouseArt(id="art-buttons")
                        yield Static("", id="caption", classes="caption")
                    with Vertical(classes="controls"):
                        yield DataTable(id="buttons", cursor_type="row", zebra_stripes=False)
                        yield Static("", id="buttons-hint", classes="keys")
            with TabPane("LIGHTING", id="lighting-tab"):
                with Horizontal(classes="page"):
                    with Vertical(classes="art-column"):
                        yield MouseArt(id="art-light")
                    yield VerticalScroll(id="lighting", classes="controls")
            with TabPane("PERFORMANCE", id="performance-tab"):
                yield VerticalScroll(id="performance")
        yield Footer()

    async def on_mount(self):
        self.register_theme(THEME)
        self.theme = "hyprmouse"
        table = self.query_one("#buttons", DataTable)
        table.add_column("BUTTON", key="button")
        table.add_column("ACTION", key="does")
        table.add_column("", key="detail")
        try:
            hypr.ensure_wiring()
            added = integration.ensure()
            if added:
                self.notify("Added " + " and ".join(added) + ".", title="Set up for Omarchy")
        except OSError as error:
            self.notify(f"Couldn't set up Hyprland: {error}", severity="error")
        self.hotkeys = hotkeys.load()
        self.sync_hyprland()
        await self.scan()
        self.set_interval(2.0, self.scan)

    # Devices

    async def scan(self):
        mice = devices.find_mice()
        signature = tuple((m.id, m.control, tuple(m.button_codes())) for m in mice)
        if signature == self.signature:
            return
        self.signature = signature
        previous = self.mouse.id if self.mouse else None
        self.mice = mice
        select = self.query_one("#mouse-select", Select)
        select.set_options([(m.name, i) for i, m in enumerate(mice)])
        select.display = len(mice) > 1
        index = next((i for i, m in enumerate(mice) if m.id == previous), 0)
        await self.use_mouse(mice[index] if mice else None)
        if len(mice) > 1:
            select.value = index

    @on(Select.Changed, "#mouse-select")
    async def mouse_selected(self, event):
        if isinstance(event.value, int) and self.mice and self.mice[event.value] is not self.mouse:
            await self.use_mouse(self.mice[event.value])

    async def use_mouse(self, mouse):
        if self.driver:
            self.driver.close()
        self.mouse, self.driver, self.onboard, self.light = mouse, None, {}, {}
        empty = mouse is None
        self.query_one("#empty").display = empty
        self.query_one("#tabs").display = not empty
        self.query_one("#device", Label).update(mouse.name if mouse else "")
        if empty:
            self.query_one("#banner").display = False
            return

        if mouse.supported:
            try:
                self.driver = mouse.driver_class(mouse)
                self.onboard = {code: self.driver.get_button(code)
                                for code in mouse.profile.buttons if code in mouse.buttons}
            except PermissionError:
                self.driver = None
            except DEVICE_ERRORS as error:
                self.driver = None
                self.notify(f"Couldn't read the mouse's settings: {error}", severity="warning")

        profile = mouse.profile
        tabs = self.query_one("#tabs", TabbedContent)
        for tab, wanted in (("lighting-tab", profile and profile.has_lighting),
                            ("performance-tab", profile and profile.has_performance)):
            (tabs.show_tab if self.driver and wanted else tabs.hide_tab)(tab)

        for art in self.query(MouseArt):
            art.buttons = set(mouse.buttons)
            art.logo = art.wheel = None
            art.refresh()
        self.update_banner()
        self.fill_buttons()
        if self.driver and profile.has_lighting:
            await self.build_lighting()
        if self.driver and profile.has_performance:
            await self.build_performance()
        self.query_one("#buttons").focus()

        if devices.needs_permission(mouse) and not self.asked_permission:
            self.asked_permission = True
            self.action_allow()

    def update_banner(self):
        banner = self.query_one("#banner", Static)
        if self.mouse and devices.needs_permission(self.mouse):
            if self.mouse.supported:
                banner.update("Lighting, sensitivity and on-mouse button settings need a one-time "
                              "permission. Press [b]A[/b] to allow.")
            else:
                banner.update("To pick a button by pressing it, press [b]A[/b] to allow access (one time).")
            banner.display = True
        else:
            banner.display = False

    def check_action(self, action, parameters):
        if action in self.BUTTON_ACTIONS:
            tabs = self.query("#tabs")
            return bool(self.mouse) and bool(tabs) and tabs.first().active == "buttons-tab"
        if action == "allow":
            return bool(self.mouse) and devices.needs_permission(self.mouse)
        return True

    @on(TabbedContent.TabActivated)
    def tab_changed(self):
        self.refresh_bindings()

    def action_allow(self):
        if not self.mouse or not devices.needs_permission(self.mouse):
            return

        async def done(granted):
            if granted:
                self.signature = None  # re-open the mouse with the new access
                await self.scan()
                self.notify("Done. omarchy-hyprmouse can now talk to your mouse.", title="Access allowed")

        self.push_screen(PermissionDialog(self.mouse), done)

    def action_tab(self, tab):
        try:
            self.query_one("#tabs", TabbedContent).active = tab
        except ValueError:
            pass

    # Buttons tab

    def button_state(self, code):
        """(what it does, detail, current choice id) for one button."""
        default = devices.DEFAULT_ACTIONS.get(code, "its normal function")
        setting = self.onboard.get(code)
        if setting is not None and setting.kind != "default":
            if setting.kind == "disabled":
                return "Does nothing", "turned off in the mouse", "disabled"
            if setting.kind == "media":
                label = drivers.MEDIA_KEYS.get(setting.value, ("A media key",))[0]
                return label, "stored in the mouse", f"media:{setting.value}"
            return setting.label or "Custom", "stored in the mouse", None

        action = self.store.button(code)
        if not action:
            return f"Default: {default}", "", "default"
        detail = hotkeys.pretty_combo(action["keys"]) if action["kind"] == "hotkey" else ""
        current = {
            "hotkey": f"hotkey:{action.get('keys')}",
            "command": "command",
            "shortcut": "shortcut",
            "disabled": "disabled",
        }.get(action["kind"])
        return hypr.describe(action), detail, current

    def fill_buttons(self):
        table = self.query_one("#buttons", DataTable)
        cursor = table.cursor_row
        table.clear()
        for code in self.mouse.button_codes():
            name = self.mouse.button_name(code)
            if code in devices.LOCKED:
                table.add_row(Text(name, style="dim"), Text(name, style="dim"),
                              Text("can't be changed", style="dim"), key=str(code))
                continue
            does, detail, _ = self.button_state(code)
            style = "dim" if does.startswith("Default") else "bold"
            table.add_row(name, Text(does, style=style), Text(detail, style="dim"), key=str(code))
        if table.row_count:
            table.move_cursor(row=min(cursor, table.row_count - 1) if cursor else self.first_editable_row())
        self.row_highlighted()

        key = "[b $accent]{}[/]"
        hint = (f"{key.format('ENTER')} change    {key.format('P')} press a button to pick it    "
                f"{key.format('D')} default    {key.format('R')} reset all")
        if len(self.mice) > 1:
            hint += "\n\nButton actions apply to every mouse plugged in."
        self.query_one("#buttons-hint", Static).update(hint)

    def first_editable_row(self):
        for index, code in enumerate(self.mouse.button_codes()):
            if code not in devices.LOCKED:
                return index
        return 0

    def selected_code(self):
        table = self.query_one("#buttons", DataTable)
        if not self.mouse or table.row_count == 0:
            return None
        return self.mouse.button_codes()[table.cursor_row]

    @on(DataTable.RowHighlighted, "#buttons")
    def row_highlighted(self):
        code = self.selected_code()
        self.query_one("#art-buttons", MouseArt).selected = code
        caption = self.query_one("#caption", Static)
        if code is None:
            caption.update("")
            return
        text = Text(self.mouse.button_name(code).upper(), style=f"bold {GREEN}")
        text.append("\n")
        text.append(self.button_state(code)[0] if code not in devices.LOCKED else "Always clicks",
                    style="#E6E6E6")
        caption.update(text)

    @on(DataTable.RowSelected, "#buttons")
    def row_selected(self):
        self.action_change()

    def action_change(self, code=None):
        if not self.mouse or self.query_one("#tabs", TabbedContent).active != "buttons-tab":
            return
        code = code if code is not None else self.selected_code()
        if code is None:
            return
        name = self.mouse.button_name(code)
        if code in devices.LOCKED:
            self.notify(f"{name} can't be changed, so you can always click.", title=name)
            return
        _, _, current = self.button_state(code)
        picker = ActionPicker(
            name,
            devices.DEFAULT_ACTIONS.get(code, "normal function"),
            current,
            self.hotkeys,
            media_keys=self.driver.media_keys() if self.driver and code in self.onboard else {},
            existing=self.store.button(code),
        )

        def chosen(choice):
            if not choice:
                return
            if code == devices.BTN_MIDDLE and choice["kind"] != "default" and current == "default":
                self.push_screen(
                    ConfirmDialog(
                        "Change the wheel click?",
                        "The wheel click will stop doing middle click: no more pasting with it or "
                        "opening links in a new tab.",
                        "Change it",
                    ),
                    lambda ok: ok and self.assign(code, choice),
                )
            else:
                self.assign(code, choice)

        self.push_screen(picker, chosen)

    def assign(self, code, choice):
        name = self.mouse.button_name(code)
        kind = choice["kind"]
        onboard = code in self.onboard
        previous = self.store.button(code)
        try:
            if onboard:
                # The mouse sends its normal button for everything Hyprland handles.
                if kind == "media":
                    target = drivers.media(choice["usage"])
                elif kind == "disabled":
                    target = drivers.DISABLED
                else:
                    target = drivers.DEFAULT
                if self.onboard[code] != target:
                    self.driver.set_button(code, target)
                    self.onboard[code] = target

            if kind in ("hotkey", "command", "shortcut") or (kind == "disabled" and not onboard):
                action = dict(choice)
            else:
                action = None
            self.store.set_button(code, action)
            errors = hypr.apply(self.store.buttons, devices.BUTTON_NAMES)
        except DEVICE_ERRORS as error:
            self.notify(f"Couldn't change {name}: {error}", severity="error", title="Not saved")
            self.fill_buttons()
            return

        if errors:
            self.store.set_button(code, previous)
            self.notify("Hyprland didn't accept the change:\n" + "\n".join(errors[:3]),
                        severity="error", title="Not saved")
        else:
            self.notify(f"{name}: {self.button_state(code)[0]}", title="Saved")
        self.fill_buttons()

    def action_reset_button(self):
        code = self.selected_code()
        if code is None or code in devices.LOCKED or self.query_one("#tabs").active != "buttons-tab":
            return
        self.assign(code, {"kind": "default"})

    def action_reset_all(self):
        if not self.mouse:
            return

        def confirmed(ok):
            if ok:
                for code in self.mouse.button_codes():
                    if code not in devices.LOCKED:
                        self.assign(code, {"kind": "default"})

        self.push_screen(
            ConfirmDialog("Reset all buttons?",
                          f"Every button on your {self.mouse.name} goes back to what it did out of the box.",
                          "Reset"),
            confirmed,
        )

    def action_identify(self):
        if not self.mouse:
            return
        if not any(os.access(node, os.R_OK) for node in self.mouse.event_nodes):
            self.notify("Picking by pressing needs access to the mouse first. Press A to allow.",
                        severity="warning")
            return
        self.query_one("#tabs", TabbedContent).active = "buttons-tab"

        def pressed(code):
            if code is None:
                return
            if code == -1:
                self.notify("No press seen. If a button does nothing at all, it may be turned off "
                            "in the mouse; pick it from the list instead.", severity="warning")
                return
            usage = drivers.media_usage_for_key(code)
            if usage is not None:  # a button the mouse turned into a media key
                code = next((c for c, s in self.onboard.items() if s.kind == "media" and s.value == usage), None)
            if code is None or code not in self.mouse.buttons:
                self.notify("That button isn't one this app can change.", severity="warning")
                return
            self.query_one("#buttons", DataTable).move_cursor(row=self.mouse.button_codes().index(code))
            self.action_change(code)

        self.push_screen(IdentifyDialog(self.mouse), pressed)

    # Hyprland

    def sync_hyprland(self):
        """Rewrite the bindings file if it drifted (e.g. after `omarchy refresh hyprland`)."""
        wanted = hypr.render(self.store.buttons, devices.BUTTON_NAMES)
        try:
            current = open(hypr.MODULE).read()
        except OSError:
            current = None
        if current != wanted:
            errors = hypr.apply(self.store.buttons, devices.BUTTON_NAMES)
            if errors:
                self.notify("Hyprland reported: " + "; ".join(errors[:2]), severity="warning")

    # Lighting tab

    async def build_lighting(self):
        body = self.query_one("#lighting", VerticalScroll)
        await body.remove_children()
        profile = self.mouse.profile
        widgets = []
        for index, zone in enumerate(profile.zones):
            try:
                effect, brightness = self.driver.get_lighting(zone.key)
            except DEVICE_ERRORS:
                effect, brightness = None, 100
            self.state[f"effect-{zone.key}"] = effect
            self.light[zone.key] = [effect, brightness]
            widgets.append(Label(zone.name.upper(), classes="section first" if index == 0 else "section"))
            widgets.append(Horizontal(
                Label("Effect", classes="field-label"),
                RadioSet(*[Choice(e.title(), value=effect == e, name=e) for e in profile.effects],
                         id=f"effect-{zone.key}"),
                classes="field",
            ))
            widgets.append(Horizontal(
                Label("Brightness", classes="field-label"),
                Slider(brightness, 0, 100, 5, "%", id=f"brightness-{zone.key}"),
                classes="field",
            ))
        widgets.append(Static("Saved in the mouse as you change it, so it stays after unplugging "
                              "and on other computers.\n[b $accent]TAB[/] next control    "
                              "[b $accent]←/→[/] adjust", classes="hint"))
        await body.mount_all(widgets)
        self.show_light()

    def show_light(self):
        art = self.query_one("#art-light", MouseArt)
        art.logo = tuple(self.light["logo"]) if "logo" in self.light else None
        art.wheel = tuple(self.light["scroll"]) if "scroll" in self.light else None

    @on(RadioSet.Changed)
    def radio_changed(self, event):
        radio_id = event.radio_set.id or ""
        if not self.driver or self.state.get(radio_id) == event.pressed.name:
            return
        self.state[radio_id] = event.pressed.name
        try:
            if radio_id.startswith("effect-"):
                zone = radio_id.removeprefix("effect-")
                self.driver.set_effect(zone, event.pressed.name)
                self.light[zone][0] = event.pressed.name
                self.show_light()
            elif radio_id == "poll-rate":
                self.driver.set_poll_rate(int(event.pressed.name))
                self.notify(f"Polling rate: {event.pressed.label}", title="Saved")
        except DEVICE_ERRORS as error:
            self.notify(f"The mouse didn't accept that: {error}", severity="error")

    @on(Slider.Changed)
    def slider_changed(self, event):
        if not self.driver:
            return
        slider = event.slider
        if slider.id.startswith("brightness-"):
            self.light[slider.id.removeprefix("brightness-")][1] = event.value
            self.show_light()
        elif slider.id == "dpi":
            self.query_one("#dpi-readout", Static).update(big_number(event.value, "DPI"))
        # Apply after the slider settles, so holding an arrow key doesn't flood the mouse.
        if slider.id in self.pending:
            self.pending[slider.id].stop()
        self.pending[slider.id] = self.set_timer(0.25, lambda: self.apply_slider(slider))

    def apply_slider(self, slider):
        self.pending.pop(slider.id, None)
        try:
            if slider.id.startswith("brightness-"):
                self.driver.set_brightness(slider.id.removeprefix("brightness-"), slider.value)
            elif slider.id == "dpi":
                slider.set_value(self.driver.set_dpi(slider.value), notify=False)
                for button in self.query(".presets Button"):
                    button.set_class(button.id == f"dpi-{slider.value}", "current")
                self.notify(f"Pointer speed: {slider.value} DPI", title="Saved")
        except DEVICE_ERRORS as error:
            self.notify(f"The mouse didn't accept that: {error}", severity="error")

    # Performance tab

    async def build_performance(self):
        body = self.query_one("#performance", VerticalScroll)
        await body.remove_children()
        profile = self.mouse.profile
        widgets = []
        if profile.dpi:
            low, high, step = profile.dpi
            try:
                dpi = self.driver.get_dpi()
            except DEVICE_ERRORS:
                dpi = (low + high) // 2
            widgets += [
                Label("SENSITIVITY", classes="section first"),
                Static(big_number(dpi, "DPI"), id="dpi-readout"),
                Horizontal(Label("Speed", classes="field-label"),
                           Slider(dpi, low, high, step, " DPI", id="dpi"), classes="field"),
            ]
            if profile.dpi_presets:
                widgets.append(Horizontal(
                    *[Button(str(p), id=f"dpi-{p}", classes="current" if p == dpi else "")
                      for p in profile.dpi_presets],
                    classes="presets",
                ))
            widgets.append(Static("Higher DPI moves the pointer further for the same hand movement. "
                                  "Saved in the mouse.", classes="hint"))
        if profile.poll_rates:
            try:
                rate = self.driver.get_poll_rate()
            except DEVICE_ERRORS:
                rate = None
            self.state["poll-rate"] = str(rate)
            widgets += [
                Label("POLLING RATE", classes="section first" if not widgets else "section"),
                Horizontal(
                    Label("Reports", classes="field-label"),
                    RadioSet(*[Choice(f"{hz} Hz", value=rate == hz, name=str(hz)) for hz in profile.poll_rates],
                             id="poll-rate"),
                    classes="field",
                ),
                Static("How often the mouse reports movement. Higher is smoother; lower uses a little "
                       "less power.", classes="hint"),
            ]
        await body.mount_all(widgets)

    @on(Button.Pressed, ".presets Button")
    def preset(self, event):
        self.query_one("#dpi", Slider).set_value(int(event.button.id.removeprefix("dpi-")))
