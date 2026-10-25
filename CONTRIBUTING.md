# Contributing

The most useful contribution is **support for your mouse**. There are two kinds:

- **Your mouse uses a protocol we already speak** (most Razer mice): add a *profile*, a small
  TOML file. No code.
- **Your mouse is from another brand** (Logitech HID++, SteelSeries, Glorious…): add a *driver*,
  one Python module, plus a profile.

Button remapping through Hyprland already works for every mouse without either.

## Setting up

```sh
git clone https://github.com/sambuaneesh/omarchy-hyprmouse
cd omarchy-hyprmouse
sudo pacman -S --needed python-textual python-evdev lua python-pytest
python -m hyprmouse            # run the app from the checkout
python -m hyprmouse --doctor   # what it sees
python -m pytest               # tests (no mouse needed)
```

Running from a checkout uses your real `~/.config`, just like the installed package.

## Adding a mouse (new profile)

1. **Find its USB id**: `lsusb` shows e.g. `ID 1532:0098 Razer USA, Ltd ...`.

2. **Start from the closest profile.** Copy one from `hyprmouse/profiles/<vendor>/` into
   `~/.config/omarchy-hyprmouse/profiles/`, then change `name` and `usb`. Profiles there override
   built-in ones, so you can test without touching the installed package.

3. **Give your session access**: open the app. It offers a one-time setup for mice that the
   packaged udev rule doesn't cover yet.

4. **Find the button ids and lights.**

   ```sh
   omarchy-hyprmouse --doctor --scan
   ```

   lists the onboard buttons and lighting LEDs that answer, with their current settings. The scan
   only reads. Match the button ids to physical buttons: in the app, set a button to *Do nothing*
   and see which one stops working, or compare with OpenRazer's `razermouse_driver.c` for your
   model.

5. **Try everything in the app**: each button's actions, every lighting effect, DPI and polling
   rate. Unplug and replug, and check that the settings stuck.

6. **Send it in**: move the file to `hyprmouse/profiles/<vendor>/<model>.toml`, regenerate the
   packaged udev rule and run the tests:

   ```sh
   python -m hyprmouse --udev-rules > packaging/70-omarchy-hyprmouse.rules   # with no user profiles
   python -m pytest
   ```

   Say in the first line of the profile whether it was verified on real hardware.

### Profile format

```toml
name = "Razer DeathAdder Essential (2021)"   # shown in the app
driver = "razer"                              # a module in hyprmouse/drivers/
usb = ["1532:0098"]                           # vendor:product, hex; several allowed

# Buttons whose function is stored in the mouse. Keyed by the Linux button code the
# button sends by default: 274 wheel click, 275 side/back, 276 side/forward,
# 277 forward, 278 back, 279 task. Left/right click (272/273) are never remapped.
[buttons.275]
name = "Side button, rear"
id = 0x04            # the driver's own id for this button
# native = 4         # mouse button number it sends by default (derived from the code)

[lighting]                                    # omit if the mouse has no lights
effects = ["static", "breathing", "off"]
zones = [{ key = "logo", name = "Logo", led = 0x04 }]   # key: "logo" or "scroll" (drawn on the mouse)

[performance]                                 # omit what the mouse can't do
dpi = [100, 6400, 100]                        # min, max, step
dpi_presets = [400, 800, 1600, 3200, 6400]
poll_rates = [125, 500, 1000]

[razer]                                       # options for the driver, named after it
interface = 0
transaction_id = { buttons = 0x1F, misc = 0xFF, lighting = 0x3F }
```

Extra keys inside a lighting zone (like `led`) are passed to the driver.

## Adding a brand (new driver)

1. Create `hyprmouse/drivers/<brand>.py` with a `Driver` subclass and decorate it with
   `@register`. Implement what your mice can do: `control_node`, and any of `get_button` /
   `set_button`, `media_keys`, `get_lighting` / `set_effect` / `set_brightness`,
   `get_dpi` / `set_dpi`, `get_poll_rate` / `set_poll_rate`, and `scan` for `--doctor --scan`.
   `hyprmouse/drivers/razer.py` is the reference.
2. Import it at the bottom of `hyprmouse/drivers/__init__.py`.
3. Add a profile with `driver = "<brand>"` and an options table `[<brand>]`.

Buttons are exchanged as `ButtonSetting`s (`default`, `disabled`, `media`, `other`), so the UI never
needs to know your protocol. The app only shows features the profile declares, and calls the driver
only when the user changes something.

**Ground rules for drivers:**

- Only ever change *settings*. Never touch firmware updates, bootloaders or calibration.
- Read every write back, and raise `DriverError` if the mouse didn't keep it.
- Keep protocol notes and sources (OpenRazer, Solaar, libratbag, your own captures) in the
  module docstring.
- Put pure logic (report building, encoding) in plain functions and test it in `tests/`.

## Code map

| Path | |
| --- | --- |
| `hyprmouse/app.py` | the TUI |
| `hyprmouse/dialogs.py`, `widgets.py`, `art.py` | action picker and other dialogs, controls, the mouse drawing |
| `hyprmouse/devices.py` | finds mice in sysfs and matches profiles |
| `hyprmouse/profiles.py`, `profiles/` | profile loading/validation, built-in profiles, udev rule generation |
| `hyprmouse/drivers/` | hardware drivers |
| `hyprmouse/hotkeys.py`, `data/extract_hotkeys.lua` | lists Omarchy hotkeys for the picker |
| `hyprmouse/hypr.py`, `data/capture.lua` | Hyprland wiring and the generated `hyprmouse.lua` |
| `hyprmouse/integration.py` | Omarchy menu entry and repair hooks |
| `hyprmouse/permissions.py` | udev `uaccess` rules for mice |
| `packaging/` | udev rule, desktop entry, AUR PKGBUILD |

## Pull requests

Keep them focused, run `python -m pytest`, and for hardware changes include the
`omarchy-hyprmouse --doctor` output from your mouse.
