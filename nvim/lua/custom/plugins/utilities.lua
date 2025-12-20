return {
  {
    'startup-nvim/startup.nvim',
    dependencies = { 'nvim-telescope/telescope.nvim', 'nvim-lua/plenary.nvim', 'nvim-telescope/telescope-file-browser.nvim' },
    priority = 100,
    lazy = false,
    config = function()
      require('startup').setup {
        -- Choose a theme (basic, dashboard, or empty)
        theme = 'evil',

        -- Configure sections
        sections = {
          {
            type = 'text',
            title = 'Header',
            align = 'center',
            fold_section = false,
            margin = 5,
            content = {
              'Welcome to Neovim',
            },
          },
          {
            type = 'mapping',
            title = 'Quick links',
            align = 'center',
            fold_section = false,
            margin = 5,
            content = {
              { ' Find File', 'Telescope find_files', '<leader>ff' },
              { ' Recent Files', 'Telescope oldfiles', '<leader>of' },
              { ' File Browser', 'Telescope file_browser', '<leader>fb' },
            },
          },
        },

        options = {
          mapping_keys = true, -- Display mapping (e.g. <leader>ff)
          cursor_column = 0.5, -- Cursor column (0 to 1, 0 being left, 0.5 center)
          empty_lines_between_mappings = true,
          disable_statuslines = true,
          paddings = { 1, 3, 3, 0 },
        },

        mappings = {
          execute_command = '<CR>',
          open_file = 'o',
          open_file_split = '<c-o>',
          open_section = '<TAB>',
          open_help = '?',
        },

        colors = {
          background = '#1f2227',
          folded_section = '#56b6c2',
        },

        parts = { 'section_1', 'section_2' },
      }
    end,
  },
  { 'mg979/vim-visual-multi' },
  {
    'rcarriga/nvim-notify',
    config = function()
      vim.notify = require 'notify'
    end,
  },
  {
    'ThePrimeagen/harpoon',
    branch = 'harpoon2',
    dependencies = { 'nvim-lua/plenary.nvim' },
  },
  {
    'akinsho/toggleterm.nvim',
    version = '*',
    config = function()
      require('toggleterm').setup {
        direction = 'vertical',
        size = 70,
        start_in_insert = true,
        persist_mode = true, -- keep in insert mode if you left it that way
        close_on_exit = false, -- don't kill terminal on close
        shell = vim.o.shell, -- use default shell
        shading_factor = 2,
      }

      -- Esc to normal mode in terminal
      vim.keymap.set('t', '<Esc>', [[<C-\><C-n>]], { noremap = true })

      -- Toggle terminal with <leader>`
      vim.keymap.set('n', '<leader>`', '<cmd>ToggleTerm<CR>', { desc = 'Toggle terminal' })
      vim.keymap.set('t', '<leader>`', [[<C-\><C-n><cmd>ToggleTerm<CR>]], { desc = 'Toggle terminal (from term)' })
    end,
  },
  'ThePrimeagen/vim-be-good',
  {
    'NickvanDyke/opencode.nvim',
    dependencies = { 'folke/snacks.nvim' },
    opts = {
      -- Fixed syntax; keep false to match your setup, or set to true for auto-launch in embedded terminal
      ['auto-fallback-to-embedded'] = false,
      -- Optional: Extend contexts with customs (add more as needed)
      context = {
        -- Example: Custom placeholder for entire project files (requires scripting or external tools)
        ['@project'] = function()
          return vim.fn.system 'git ls-files'
        end,
      },
      -- Optional: Add custom prompts for select_prompt()
      prompts = {
        'Explain the code: @cursor',
        'Refactor this: @selection',
        'Generate tests for: @buffer',
      },
    },
    keys = {
      -- Basic ask (improved with cursor context)
      {
        '<leader>oa',
        function()
          require('opencode').ask '@cursor: '
        end,
        desc = 'Ask opencode about cursor',
        mode = 'n',
      },
      -- Visual mode (unchanged, but consistent)
      {
        '<leader>oa',
        function()
          require('opencode').ask '@selection: '
        end,
        desc = 'Ask opencode about selection',
        mode = 'v',
      },
      -- Toggle embedded terminal (useful if auto-fallback is false)
      {
        '<leader>ot',
        function()
          require('opencode').toggle()
        end,
        desc = 'Toggle embedded opencode',
        mode = 'n',
      },
      -- New session
      {
        '<leader>on',
        function()
          require('opencode').command 'session_new'
        end,
        desc = 'New opencode session',
        mode = 'n',
      },
      -- Copy last message
      {
        '<leader>oy',
        function()
          require('opencode').command 'messages_copy'
        end,
        desc = 'Copy last opencode message',
        mode = 'n',
      },
      -- Scroll messages (use in opencode buffer)
      {
        '<S-C-u>',
        function()
          require('opencode').command 'messages_half_page_up'
        end,
        desc = 'Scroll opencode messages up',
        mode = 'n',
      },
      {
        '<S-C-d>',
        function()
          require('opencode').command 'messages_half_page_down'
        end,
        desc = 'Scroll opencode messages down',
        mode = 'n',
      },
      -- Select from prompts (normal and visual)
      {
        '<leader>op',
        function()
          require('opencode').select_prompt()
        end,
        desc = 'Select opencode prompt',
        mode = { 'n', 'v' },
      },
      -- Example custom: Explain near cursor
      {
        '<leader>oe',
        function()
          require('opencode').ask '@buffer\nExplain the code near the cursor:\n@cursor'
        end,
        desc = 'Explain code near cursor',
        mode = 'n',
      },
    },
  },
}
