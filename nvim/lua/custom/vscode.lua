-- VSCode-specific configuration
local M = {}

-- VSCode-specific keymaps
M.setup_keymaps = function()
  local map = vim.keymap.set

  -- Basic navigation and editing
  map('n', '<C-j>', '<C-w>j', { desc = 'Move focus to the lower window' })
  map('n', '<C-k>', '<C-w>k', { desc = 'Move focus to the upper window' })
  map('n', '<C-h>', '<C-w>h', { desc = 'Move focus to the left window' })
  map('n', '<C-l>', '<C-w>l', { desc = 'Move focus to the right window' })

  -- Text manipulation
  map('x', 'J', ":move '>+1<CR>gv-gv", { desc = 'move selected lines down' })
  map('x', 'K', ":move '<-2<CR>gv-gv", { desc = 'move selected lines up' })

  -- VSCode-specific commands
  map('n', '<leader>f', "<Cmd>call VSCodeNotify('workbench.action.quickOpen')<CR>", { desc = 'Quick Open' })
  map('n', '<leader>e', "<Cmd>call VSCodeNotify('workbench.action.toggleSidebarVisibility')<CR>", { desc = 'Toggle Sidebar' })
  map('n', '<leader>b', "<Cmd>call VSCodeNotify('workbench.action.toggleActivityBarVisibility')<CR>", { desc = 'Toggle Activity Bar' })
  map('n', '<leader>p', "<Cmd>call VSCodeNotify('workbench.action.showCommands')<CR>", { desc = 'Show Commands' })
end

return M 