"""Top-down drawing of the mouse, with buttons and the logo that light up."""

import math

from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

GREEN = (0x44, 0xD6, 0x2C)

# Letters mark regions: L/R main buttons, W wheel, F/B front/rear side buttons,
# 1-6 the logo. "." is the palm. Everything else is drawn as-is (the outline).
TEMPLATE = [
    "    ╭────────┬───┬────────╮",
    "   ╱LLLLLLLLL│ W │RRRRRRRRR╲",
    "  │LLLLLLLLLL│ W │RRRRRRRRRR│",
    "  │LLLLLLLLLL│ W │RRRRRRRRRR│",
    "  │LLLLLLLLLL╰───╯RRRRRRRRRR│",
    "  │LLLLLLLLLLLL│RRRRRRRRRRRR│",
    "  │LLLLLLLLLLLL│RRRRRRRRRRRR│",
    "  ├────────────┴────────────┤",
    " F│.........................│",
    " F│.........................│",
    "  │.........................│",
    " B│.........................│",
    " B│.........................│",
    "  │...........123...........│",
    "  │...........456...........│",
    "  │.........................│",
    "  │.........................│",
    "   ╲.......................╱",
    "    ╲.....................╱",
    "     ╰───────────────────╯",
]
WIDTH = max(len(line) for line in TEMPLATE)

REGION_CODES = {"L": 272, "R": 273, "W": 274, "B": 275, "F": 276}
LOGO = dict(zip("123456", "▟█▙▜█▛"))


def _mix(rgb, amount, base=(0x26, 0x26, 0x26)):
    r, g, b = (round(base[i] + (rgb[i] - base[i]) * amount) for i in range(3))
    return f"#{r:02x}{g:02x}{b:02x}"


class MouseArt(Widget):
    DEFAULT_CSS = """
    MouseArt { width: 31; height: 23; padding: 1 0 0 1; }
    """

    selected = reactive(None)  # Linux button code to light up
    logo = reactive(None)  # None (no lighting), or (effect, brightness 0-100)
    wheel = reactive(None)  # scroll-wheel lighting, same form as logo
    phase = reactive(0.0)

    def __init__(self, buttons=(), **kwargs):
        super().__init__(**kwargs)
        self.buttons = set(buttons)
        self._breath_timer = None

    def on_mount(self):
        self._breath_timer = self.set_interval(1 / 15, self._tick, pause=True)

    def watch_logo(self):
        self._sync_breathing()

    def watch_wheel(self):
        self._sync_breathing()

    def _sync_breathing(self):
        if self._breath_timer:
            if any(state and state[0] == "breathing" for state in (self.logo, self.wheel)):
                self._breath_timer.resume()
            else:
                self._breath_timer.pause()

    def _tick(self):
        self.phase = (self.phase + 1 / 45) % 1.0  # one breath every ~3 seconds

    def _light_style(self, state):
        if not state:
            return None
        effect, brightness = state
        level = brightness / 100
        if effect == "off":
            return "#2a2a2a"
        if effect == "breathing":
            level *= 0.5 - 0.5 * math.cos(self.phase * 2 * math.pi)
        return f"bold {_mix(GREEN, max(0.08, level))}"

    def render(self):
        outline = "#5a5a5a"
        idle_button = "#7a7a7a"
        lit = f"bold #{GREEN[0]:02x}{GREEN[1]:02x}{GREEN[2]:02x}"
        tint = "on #163d10"
        logo_style = self._light_style(self.logo)
        wheel_style = self._light_style(self.wheel)

        text = Text(no_wrap=True)
        for row, line in enumerate(TEMPLATE):
            for ch in line.ljust(WIDTH):
                code = REGION_CODES.get(ch)
                if code is not None:
                    present = code in self.buttons
                    chosen = code == self.selected
                    if ch in "LR":
                        text.append(" ", tint if chosen else "")
                    elif ch == "W":
                        text.append("█", lit if chosen else wheel_style or idle_button)
                    elif present:
                        text.append("▐", lit if chosen else idle_button)
                    else:
                        text.append(" ")
                elif ch in LOGO:
                    text.append(LOGO[ch] if logo_style else " ", logo_style or "")
                elif ch == ".":
                    text.append(" ")
                else:
                    text.append(ch, outline)
            if row < len(TEMPLATE) - 1:
                text.append("\n")
        return text
