-- Run: nvim --headless '+luafile nvim/tests/smoke.lua'
local failures = {}
local function check(name, callback)
 local ok, err = pcall(callback)
 if ok then
  print('PASS: ' .. name)
 else
  failures[#failures + 1] = name .. ': ' .. tostring(err)
  print('FAIL: ' .. failures[#failures])
 end
end

check('startup completes without errors', function()
 assert(vim.v.errmsg == '', vim.v.errmsg)
 assert(not vim.api.nvim_exec2('messages', { output = true }).output:find('Failed to run', 1, true))
end)

check('notifications reach message history', function()
 vim.notify('blackwall-notification-smoke', vim.log.levels.INFO)
 vim.wait(100)
 assert(vim.api.nvim_exec2('messages', { output = true }).output:find('blackwall-notification-smoke', 1, true), 'notification was swallowed')
end)

check('custom LSP settings and completion capabilities are applied', function()
 assert(vim.lsp.config.lua_ls.settings.Lua.completion.callSnippet == 'Replace')
 assert(vim.lsp.config.pyright.settings.python.analysis.autoImportCompletions == true)
 assert(vim.lsp.config.lua_ls.capabilities.textDocument.completion.completionItem.snippetSupport == true)
end)

check('TypeScript root discovery uses the native callback API', function()
 local root
 vim.lsp.config.ts_ls.root_dir(vim.api.nvim_get_current_buf(), function(dir) root = dir end)
 assert(type(root) == 'string' and root ~= '', 'root callback was not called')
end)

check('repository finder can search its configured directories', function()
 local opts = vim.deepcopy(require('telescope._extensions.repo.config').values.list)
 local command = require('telescope._extensions.repo.list').prepare_command(opts)
 local result = vim.system(command, { text = true }):wait(10000)
 assert(result.code == 0, result.stderr)
end)

check('Treesitter highlights Lua buffers', function()
 vim.cmd.enew()
 vim.api.nvim_buf_set_lines(0, 0, -1, false, { 'local example = 1' })
 vim.bo.filetype = 'lua'
 assert(vim.treesitter.highlighter.active[vim.api.nvim_get_current_buf()], 'highlighting did not start')
end)

check('filetypes without a parser remain usable', function()
 vim.cmd.enew({ bang = true })
 vim.bo.filetype = 'blackwall_unknown_filetype'
end)

if #failures > 0 then
 vim.cmd('cquit 1')
else
 vim.cmd('qa!')
end
