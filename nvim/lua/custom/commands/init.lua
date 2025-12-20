local is_vscode = vim.g.vscode == 1

if not is_vscode then
  require('custom.commands.theme')
end