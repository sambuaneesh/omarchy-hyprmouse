-- Lists every described hotkey in the user's Hyprland config, one per line:
--   <keys>\t<description>
-- Runs the config in plain Lua with a stubbed `hl`, the same way Omarchy's
-- keybindings menu does, so nothing is dispatched.

local noop
noop = setmetatable({}, {
  __index = function() return noop end,
  __call = function() return noop end,
})

-- hl.dsp.anything.chain(...) must yield a plain table: Omarchy's helpers probe
-- dispatcher tables for fields like `.launch`.
local dsp
dsp = setmetatable({}, {
  __index = function() return dsp end,
  __call = function() return {} end,
})

local order, found = {}, {}

local function normalize(keys)
  local rank = { SUPER = 1, CTRL = 2, CONTROL = 2, ALT = 3, SHIFT = 4 }
  local mods, key = {}, ""
  for part in tostring(keys or ""):gmatch("[^+]+") do
    local value = part:gsub("^%s+", ""):gsub("%s+$", ""):upper()
    if value == "CONTROL" then value = "CTRL" end
    if rank[value] then mods[#mods + 1] = value elseif value ~= "" then key = value end
  end
  table.sort(mods, function(a, b) return rank[a] < rank[b] end)
  mods[#mods + 1] = key
  return table.concat(mods, "+")
end

hl = setmetatable({
  dsp = dsp,
  bind = function(keys, _, opts)
    opts = type(opts) == "table" and opts or {}
    local id = normalize(keys)
    if opts.release or id:find("^MOUSE") or id:find("+MOUSE", 1, true) then return noop end
    if opts.description and opts.description ~= "" then
      if not found[id] then order[#order + 1] = id end
      found[id] = opts.description
    end
    return noop
  end,
  unbind = function(keys)
    found[normalize(keys)] = nil
    return noop
  end,
  get_config = function() return nil end,
}, { __index = function() return noop end })

local ok, err = pcall(dofile, os.getenv("HOME") .. "/.config/hypr/hyprland.lua")
if not ok then io.stderr:write(tostring(err) .. "\n") end

for _, id in ipairs(order) do
  if found[id] then print(id .. "\t" .. found[id]) end
end
