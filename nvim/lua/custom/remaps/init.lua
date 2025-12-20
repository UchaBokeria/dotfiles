---@diagnostic disable: different-requires
-- Tools
local map = vim.keymap.set
local is_vscode = vim.g.vscode == 1

require 'custom.remaps.telescope'
require 'custom.remaps.opencode'

map('n', '<C-z>', '<Nop>', { noremap = true, silent = true })

-- General mappings that work in both environments
map('v', '<leader>w', function()
  local keys = vim.api.nvim_replace_termcodes('vbvel', true, false, true)
  vim.api.nvim_feedkeys(keys, 'n', false)
end, { desc = 'Select word with extra char' })

map('v', '<leader>"', function()
  local esc = vim.api.nvim_replace_termcodes('<Esc>', true, false, true)
  vim.api.nvim_feedkeys(esc, 'x', false)
  vim.cmd 'normal! `<i"'
  vim.cmd 'normal! `>a"'
end, { desc = 'Wrap in double quotes' })

map('v', "<leader>'", function()
  local esc = vim.api.nvim_replace_termcodes('<Esc>', true, false, true)
  vim.api.nvim_feedkeys(esc, 'x', false)
  vim.cmd "normal! `<i'"
  vim.cmd "normal! `>a'"
end, { desc = 'Wrap in double quotes' })

-- Text manipulations that work in both environments
map('x', 'J', ":move '>+1<CR>gv-gv", { desc = 'move selected lines down' })
map('x', 'K', ":move '<-2<CR>gv-gv", { desc = 'move selected lines up' })

-- Only load Neovim-specific mappings when not in VSCode
if not is_vscode then
  -- Harpoon
  local harpoon = require 'harpoon'
  harpoon:setup()

  -- Harpoon telescope integration
  local conf = require('telescope.config').values
  local function toggle_telescope(harpoon_files)
    local file_paths = {}
    for _, item in ipairs(harpoon_files.items) do
      table.insert(file_paths, item.value)
    end

    require('telescope.pickers')
      .new({}, {
        prompt_title = 'Harpoon',
        finder = require('telescope.finders').new_table {
          results = file_paths,
        },
        previewer = conf.file_previewer {},
        sorter = conf.generic_sorter {},
      })
      :find()
  end

  -- map('n', '<leader>a', function() end, { desc = 'Harpoon' })
  map('n', '<leader>q', function()
    harpoon:list():prev()
  end)
  map('n', '<leader>e', function()
    harpoon:list():next()
  end)

  map('n', '<leader>aR', function()
    harpoon:list():clear()
  end, { desc = 'Remove all files from the list' })

  map('n', '<leader>ar', function()
    harpoon:list():remove()
  end, { desc = 'Remove current file from the list' })

  map('n', '<leader>aa', function()
    harpoon:list():add()
  end, { desc = 'Harpoon add file in the list' })

  map('n', '<leader>ae', function()
    toggle_telescope(harpoon:list())
  end, { desc = 'Open harpoon window' })

  map('n', '<leader>1', function()
    harpoon:list():select(1)
  end)
  map('n', '<leader>2', function()
    harpoon:list():select(2)
  end)
  map('n', '<leader>3', function()
    harpoon:list():select(3)
  end)
  map('n', '<leader>4', function()
    harpoon:list():select(4)
  end)
  map('n', '<leader>5', function()
    harpoon:list():select(5)
  end)
  map('n', '<leader>6', function()
    harpoon:list():select(6)
  end)
  map('n', '<leader>7', function()
    harpoon:list():select(7)
  end)
  map('n', '<leader>8', function()
    harpoon:list():select(8)
  end)
  map('n', '<leader>9', function()
    harpoon:list():select(9)
  end)

   -- Toggle previous & next buffers stored within Harpoon list

   -- Quickfix toggle function
   local function toggle_quickfix()
     local qf_exists = false
     for _, win in ipairs(vim.fn.getwininfo()) do
       if win.quickfix == 1 then
         qf_exists = true
         break
       end
     end
     if qf_exists then
       vim.cmd('cclose')
     else
       vim.cmd('copen')
     end
   end

   -- Diagnostic keymaps
   map('n', '<leader>dd', vim.diagnostic.open_float, { desc = 'Show diagnostic details' })
   map('n', '<leader>dp', require('telescope.builtin').diagnostics, { desc = 'Preview diagnostics in telescope' })
   map('n', '<leader>dn', vim.diagnostic.goto_next, { desc = 'Next diagnostic' })
   map('n', '<leader>dN', vim.diagnostic.goto_prev, { desc = 'Previous diagnostic' })
   map('n', '<leader>da', vim.lsp.buf.code_action, { desc = 'Apply code action/fix' })
   map('n', '<leader>dl', vim.diagnostic.setloclist, { desc = 'Open diagnostic location list' })

   -- Quickfix keymaps
   map('n', '<leader>i', toggle_quickfix, { desc = 'Toggle quickfix window' })
   map('n', '<leader>il', vim.diagnostic.setqflist, { desc = 'Open diagnostic quickfix list' })
   map('n', '<leader>in', '<cmd>cnext<CR>', { desc = 'Next quickfix item' })
   map('n', '<leader>iN', '<cmd>cprev<CR>', { desc = 'Previous quickfix item' })
   map('n', '<leader>ip', require('telescope.builtin').quickfix, { desc = 'Preview quickfix in telescope' })
   map('n', '<leader>io', '<cmd>copen<CR>', { desc = 'Open quickfix window' })
   end
