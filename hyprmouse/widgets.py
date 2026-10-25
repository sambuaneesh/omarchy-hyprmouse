"""Small building blocks for the UI: theme, slider, radio option, big digits."""

from rich.text import Text
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive
from textual.theme import Theme
from textual.widget import Widget
from textual.widgets import RadioButton

GREEN = "#44D62C"

THEME = Theme(
    name="hyprmouse",
    primary=GREEN,
    secondary="#2E8B1F",
    accent=GREEN,
    foreground="#E6E6E6",
    background="#0A0A0A",
    surface="#121212",
    panel="#262626",
    success=GREEN,
    warning="#F5A623",
    error="#FF4D4D",
    dark=True,
    variables={
        "text-muted": "#8A8A8A",
        "border": GREEN,
        "footer-key-foreground": GREEN,
        "footer-description-foreground": "#9A9A9A",
        "block-cursor-background": GREEN,
        "block-cursor-foreground": "#0A0A0A",
        "input-selection-background": "#44D62C40",
        "scrollbar": "#262626",
        "scrollbar-hover": "#3a3a3a",
        "scrollbar-active": GREEN,
    },
)

# Big digits for the DPI readout.
DIGITS = {
    "0": ("┏━┓", "┃ ┃", "┗━┛"), "1": ("╺┓ ", " ┃ ", "╺┻╸"), "2": ("┏━┓", "┏━┛", "┗━╸"),
    "3": ("┏━┓", " ━┫", "┗━┛"), "4": ("╻ ╻", "┗━┫", "  ╹"), "5": ("┏━╸", "┗━┓", "┗━┛"),
    "6": ("┏━╸", "┣━┓", "┗━┛"), "7": ("┏━┓", "  ┃", "  ╹"), "8": ("┏━┓", "┣━┫", "┗━┛"),
    "9": ("┏━┓", "┗━┫", "┗━┛"),
}


def big_number(value, unit):
    rows = ["", "", ""]
    for ch in str(value):
        for i in range(3):
            rows[i] += DIGITS[ch][i] + " "
    text = Text()
    for i, row in enumerate(rows):
        text.append(row, f"bold {GREEN}")
        if i == 2:
            text.append(f" {unit}", "bold #8A8A8A")
        if i < 2:
            text.append("\n")
    return text


class Slider(Widget, can_focus=True):
    """A keyboard and mouse friendly horizontal slider."""

    BINDINGS = [
        Binding("left,h", "step(-1)", "Less", show=False),
        Binding("right,l", "step(1)", "More", show=False),
        Binding("shift+left,pagedown", "step(-10)", show=False),
        Binding("shift+right,pageup", "step(10)", show=False),
        Binding("home", "jump(0)", show=False),
        Binding("end", "jump(1)", show=False),
    ]

    COMPONENT_CLASSES = {"slider--filled", "slider--empty", "slider--knob"}

    DEFAULT_CSS = """
    Slider { height: 1; width: 1fr; min-width: 20; }
    Slider > .slider--filled { color: $accent; }
    Slider > .slider--empty { color: $panel-lighten-2; }
    Slider > .slider--knob { color: $text; text-style: bold; }
    Slider:focus > .slider--knob { color: $accent; }
    Slider:focus { background: $boost; }
    """

    value = reactive(0)

    class Changed(Message):
        def __init__(self, slider, value):
            super().__init__()
            self.slider = slider
            self.value = value

        @property
        def control(self):
            return self.slider

    def __init__(self, value, minimum, maximum, step, unit="", **kwargs):
        super().__init__(**kwargs)
        self.minimum, self.maximum, self.step_size, self.unit = minimum, maximum, step, unit
        self.set_reactive(Slider.value, value)

    def _track_width(self):
        return max(4, self.size.width - len(f" {self.maximum}{self.unit}") - 1)

    def render(self):
        width = self._track_width()
        span = self.maximum - self.minimum
        filled = round((self.value - self.minimum) / span * (width - 1)) if span else 0
        text = Text()
        text.append("━" * filled, self.get_component_rich_style("slider--filled"))
        text.append("●", self.get_component_rich_style("slider--knob"))
        text.append("─" * (width - 1 - filled), self.get_component_rich_style("slider--empty"))
        text.append(f" {self.value}{self.unit}")
        return text

    def set_value(self, value, notify=True):
        value = max(self.minimum, min(self.maximum, round(value / self.step_size) * self.step_size))
        if value != self.value:
            self.value = value
            if notify:
                self.post_message(self.Changed(self, value))

    def action_step(self, steps):
        self.set_value(self.value + steps * self.step_size)

    def action_jump(self, end):
        self.set_value(self.maximum if end else self.minimum)

    def on_click(self, event):
        fraction = max(0.0, min(1.0, event.x / (self._track_width() - 1)))
        self.set_value(self.minimum + fraction * (self.maximum - self.minimum))


class Choice(RadioButton):
    """Radio option drawn as a plain dot."""

    BUTTON_LEFT = ""
    BUTTON_INNER = "●"
    BUTTON_RIGHT = ""
