local map = vim.keymap.set
local is_vscode = vim.g.vscode == 1

if not is_vscode then
 local function strudel_toggle()
  -- ensure engine is running
  pcall(vim.cmd, 'StrudelLaunch')
  -- then toggle play/stop
  pcall(vim.cmd, 'StrudelToggle')
 end

 local function strudel_quit()
  pcall(vim.cmd, 'StrudelQuit')
 end

 map('n', '<leader>ss', strudel_toggle, { desc = 'Strudel launch + toggle' })
 map('n', '<leader>sq', strudel_quit, { desc = 'Strudel quit' })
end
