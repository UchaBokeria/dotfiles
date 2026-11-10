---@diagnostic disable: redundant-parameter, undefined-global

local DEFAULT_THEME = 'blackwall'

-- The choice lives outside stdpath('config') so a dotfiles checkout never
-- overwrites it and io.open never fails on a missing lua/custom/config dir.
local function state_file()
 return vim.fn.stdpath 'data' .. '/blackwall-theme.conf'
end

-- Load theme from state file
local function load_saved_theme()
 local file = io.open(state_file(), 'r')
 if file then
  local theme = file:read '*l'
  file:close()
  if theme and theme:match '%S' then
   return theme:gsub('%s+', '')
  end
 end
 return nil
end

local function persist_theme(theme)
 local file = io.open(state_file(), 'w')
 if file then
  file:write(theme .. '\n')
  file:close()
  return true
 end
 return false
end

function Theme_apply(theme, save)
 if theme and theme ~= '' then
  local ok = pcall(vim.cmd, 'colorscheme ' .. theme)
  if not ok then
   return false
  end

  if save ~= false then
   persist_theme(vim.g.colors_name or theme)
  end

  -- vim.notify('Theme: ' .. (vim.g.colors_name or theme), vim.log.levels.INFO)
  return true
 end
 return false
end

-- Initialize theme on startup. This runs after lazy.nvim has loaded the
-- plugins (VimEnter), so no per-plugin config can stomp the saved choice.
local function init()
 local saved_theme = load_saved_theme() or DEFAULT_THEME
 if saved_theme then
  Theme_apply(saved_theme, false)
 end
end

vim.api.nvim_create_autocmd('VimEnter', {
 group = vim.api.nvim_create_augroup('BlackwallRestoreTheme', { clear = true }),
 callback = function()
  init()
 end,
})

function Theme_switcher()
 local pickers = require 'telescope.pickers'
 local finders = require 'telescope.finders'
 local conf = require('telescope.config').values
 local actions = require 'telescope.actions'
 local action_state = require 'telescope.actions.state'
 local previewers = require 'telescope.previewers'

 local current_theme = vim.g.colors_name or ''
 local initial_theme = current_theme

 -- Build theme list at open time, so schemes installed after startup show up.
 local theme_entries = {}

 if current_theme ~= '' then
  table.insert(theme_entries, { current_theme .. ' 󰄬', current_theme })
 end

 for _, theme in ipairs(vim.fn.getcompletion('', 'color')) do
  if theme ~= current_theme then
   table.insert(theme_entries, { theme, theme })
  end
 end

 -- Apply theme safely
 local function preview_theme(theme)
  if theme and theme ~= '' then
   pcall(vim.cmd, 'colorscheme ' .. theme)
   -- if _G.make_nvim_transparent then
   --  _G.make_nvim_transparent()
   -- end
  end
 end

 -- Preview buffer (text only)
 local theme_previewer = previewers.new_buffer_previewer {
  title = 'Theme Preview',

  define_preview = function(self, entry)
   local bufnr = self.state and self.state.bufnr
   if type(bufnr) ~= 'number' or not vim.api.nvim_buf_is_valid(bufnr) then
    return
   end

   vim.api.nvim_buf_set_lines(bufnr, 0, -1, false, {
    '-- Theme Preview: ' .. entry.value,
    '',
    'function example(arg)',
    '  local variable = "string"',
    '  if arg > 10 then',
    '    print("Hello, World!")',
    '    return true',
    '  end',
    '  return false',
    'end',
   })

   vim.bo[bufnr].filetype = 'lua'
  end,

  teardown = function()
   if initial_theme ~= '' then
    preview_theme(initial_theme)
   end
  end,
 }

 pickers
  .new({}, {
   prompt_title = 'Switch Theme',
   finder = finders.new_table {
    results = theme_entries,
    entry_maker = function(entry)
     return {
      value = entry[2],
      display = entry[1],
      ordinal = entry[2],
     }
    end,
   },
   sorter = conf.generic_sorter {},
   previewer = theme_previewer,
   attach_mappings = function(prompt_bufnr, _)
    local picker = action_state.get_current_picker(prompt_bufnr)
    if not picker then
     return true
    end

    local last_row = picker:get_selection_row()

    local function update_preview()
     local row = picker:get_selection_row()
     if row ~= last_row then
      last_row = row
      local entry = action_state.get_selected_entry()
      if entry then
       preview_theme(entry.value)
      end
     end
    end

    -- Run once for initial selection
    vim.schedule(update_preview)

    -- Watch selection changes safely
    local timer = vim.loop.new_timer()
    timer:start(
     0,
     30,
     vim.schedule_wrap(function()
      if not picker or picker._destroyed then
       timer:stop()
       timer:close()
       return
      end
      update_preview()
     end)
    )

    actions.select_default:replace(function()
     local selection = action_state.get_selected_entry()
     actions.close(prompt_bufnr)

     if selection then
      Theme_apply(selection.value)
     elseif initial_theme ~= '' then
      Theme_apply(initial_theme)
     end
    end)

    return true
   end,
  })
  :find()
end

return {
 Theme_switcher = Theme_switcher,
 Theme_apply = Theme_apply,
}
