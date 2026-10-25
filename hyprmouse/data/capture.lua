-- hyprmouse: remembers the action behind every hotkey as it is bound, so a mouse
-- button can run exactly the same action (see hypr/hyprmouse.lua). Required
-- before Omarchy's defaults in hyprland.lua. Installed and kept up to date by
-- hyprmouse; edits here are overwritten.

local modifier_order = { SUPER = 1, CTRL = 2, CONTROL = 2, ALT = 3, SHIFT = 4 }

local function normalize(keys)
  local mods, key = {}, ""
  for part in tostring(keys or ""):gmatch("[^+]+") do
    local value = part:gsub("^%s+", ""):gsub("%s+$", ""):upper()
    if value == "CONTROL" then
      value = "CTRL"
    end
    if modifier_order[value] then
      mods[#mods + 1] = value
    elseif value ~= "" then
      key = value
    end
  end
  table.sort(mods, function(a, b)
    return modifier_order[a] < modifier_order[b]
  end)
  mods[#mods + 1] = key
  return table.concat(mods, "+")
end

-- Fresh table on every config load; Hyprland keeps the Lua state across reloads.
hyprmouse = { actions = {}, normalize = normalize }

function hyprmouse.action(keys)
  return hyprmouse.actions[normalize(keys)]
end

if not _G.__hyprmouse_bind_wrapped then
  _G.__hyprmouse_bind_wrapped = true

  local bind, unbind = hl.bind, hl.unbind
  hl.bind = function(keys, dispatcher, opts, ...)
    if not (type(opts) == "table" and opts.release) then
      hyprmouse.actions[normalize(keys)] = dispatcher
    end
    return bind(keys, dispatcher, opts, ...)
  end
  hl.unbind = function(keys, ...)
    hyprmouse.actions[normalize(keys)] = nil
    return unbind(keys, ...)
  end
end
