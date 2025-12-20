---@diagnostic disable: different-requires
local map = vim.keymap.set
local builtin = require 'telescope.builtin'

map('n', '<leader>t', '', { desc = 'Telescope' })

-- 🔍 General Operations
map('n', '<leader>tz', function()
  require('telescope').extensions.zoxide.list()
end, { desc = 'Telescope: Zoxide' })
map('n', '<leader>tb', function()
  require('telescope').extensions.bookmarks.bookmarks()
end, { desc = 'Telescope: Browser Bookmarks' })

map('n', '<leader>tq', '', { desc = 'Quickfix' })
map('n', '<leader>tqq', builtin.quickfix, { desc = 'Telescope: Quickfix' })
map('n', '<leader>tqh', builtin.quickfixhistory, { desc = 'Telescope: Quickfix History' })

map('n', '<leader>tc', '', { desc = 'Command' })
map('n', '<leader>tcc', builtin.commands, { desc = 'Telescope: Commands' })
map('n', '<leader>tch', builtin.command_history, { desc = 'Telescope: Command History' })

-- 🔍 Search Operations
map('n', '<leader>ts', '', { desc = 'Search' })
map('n', '<leader>tsg', function()
  builtin.grep_string { search = vim.fn.input 'Grep > ' }
end, { desc = 'Telescope: Search (input)' })
map('n', '<leader>tsl', builtin.live_grep, { desc = 'Telescope: Live Grep' })
map('n', '<leader>tsh', builtin.search_history, { desc = 'Telescope: Search History' })
map('n', '<leader>tso', builtin.vim_options, { desc = 'Telescope: Vim Options' })
map('n', '<leader>tsk', builtin.keymaps, { desc = 'Telescope: Keymaps' })
map('n', '<leader>tsu', function()
  require('telescope').extensions.undo.undo()
end, { desc = 'Telescope: Undo Tree' })

-- 📚 Help Operations
map('n', '<leader>th', '', { desc = 'Help' })
map('n', '<leader>tht', builtin.help_tags, { desc = 'Telescope: Help Tags' })
map('n', '<leader>thl', builtin.highlights, { desc = 'Telescope: Highlights' })
map('n', '<leader>thh', function()
  require('telescope').extensions.heading.heading()
end, { desc = 'Telescope: Markdown/Org Headings' })

-- 📂 File Operations
map('n', '<leader>tf', function()
  require('telescope').extensions.file_browser.file_browser { 
    path = vim.fn.expand('%:p:h'), 
    initial_mode = 'normal', 
    numbering = true,
    grouped = true,
    hidden = true,
    respect_gitignore = false,
  }
end, { desc = 'Telescope: File Browser' })
map('n', '<leader>tF', ':Telescope find_files<CR>')
map('n', '<leader>tr', builtin.oldfiles, { desc = 'Telescope: Recent Files' })
map('n', '<leader>tj', builtin.jumplist, { desc = 'Telescope: Jump List' })
map('n', '<leader>tp', function()
  require('telescope').extensions.project.project {}
end, { desc = 'Telescope: Projects' })
map('n', '<leader>tm', function()
  require('telescope').extensions.media_files.media_files()
end, { desc = 'Telescope: Media Files' })

-- 🌲 Git Operations
map('n', '<leader>tg', '', { desc = 'Git' })
map('n', '<leader>tgf', builtin.git_files, { desc = 'Telescope: Git Files' })
map('n', '<leader>tgc', builtin.git_commits, { desc = 'Telescope: Git Commits' })
map('n', '<leader>tgb', builtin.git_branches, { desc = 'Telescope: Git Branches' })
map('n', '<leader>tgs', builtin.git_status, { desc = 'Telescope: Git Status' })
map('n', '<leader>tgw', function()
  require('telescope').extensions.git_worktree.git_worktrees()
end, { desc = 'Telescope: Git Worktrees' })
map('n', '<leader>tgr', function()
  require('telescope').extensions.repo.list()
end, { desc = 'Telescope: Git Repos' })

-- 🐙 GitHub Integration
map('n', '<leader>tgh', '', { desc = 'Github Octo' })
map('n', '<leader>tgho', ':Octo', { desc = 'Telescope: GitHub Interface' })
map('n', '<leader>tghi', ':Octo issue list', { desc = 'Telescope: GitHub Issues' })
map('n', '<leader>tghp', ':Octo pr list', { desc = 'Telescope: GitHub PRs' })
map('n', '<leader>tghs', ':Octo search', { desc = 'Telescope: GitHub Search' })

-- Todos
map('n', '<leader>tt', ':TodoTelescope keywords=TODO,FIX<CR>', { desc = 'Telescope: Todo Search' })

-- 🎨 Theme
map('n', '<leader>tst', function()
  require('custom.utils.themes').Theme_switcher()
end, { desc = 'Telescope: Theme Switcher' })
