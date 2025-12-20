local is_vscode = vim.g.vscode == 1

if not is_vscode then
 -- Check dependencies first
 require('custom.utils.dependencies').ensure_dependencies()

 -- Load Neovim-specific features
 require 'custom.commands'
 require 'custom.remaps'
 require 'custom.plugins'

 -- local ok, file = pcall(io.open, vim.fn.stdpath 'config' .. '/lua/custom/config/theme.conf', 'r')
 -- if ok and file then
 --  local savedTheme = file:read '*l'
 --  file:close()
 --  if savedTheme and savedTheme ~= '' then
 --   vim.cmd('colorscheme ' .. savedTheme)
 --  end
 -- else
 --  print 'theme configuration has not been found!'
 -- end
else
 -- Load VSCode-specific configuration
 require('custom.vscode').setup_keymaps()
end
