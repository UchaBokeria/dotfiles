-- General
local cmd = vim.api.nvim_create_user_command
require 'custom.utils.themes'

-- Themes
cmd('SetTheme', function(opts)
  local args = opts.fargs
  if #args > 1 then
    print 'too many arguments'
    return
  end

  Theme_apply(opts.args[1])
end, { nargs = 1, complete = 'color' })
