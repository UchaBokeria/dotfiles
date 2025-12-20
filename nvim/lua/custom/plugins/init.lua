---@diagnostic disable: different-requires
local is_vscode = vim.g.vscode == 1

-- Load plugins based on environment
local function load()
  -- Base plugins that work in both environments
  local plugins = {
    { "mg979/vim-visual-multi" }, -- Works in both Neovim and VSCode
    { "windwp/nvim-autopairs", event = "InsertEnter", opts = {} }, -- Automatic bracket pairing
  }
  
  -- Only load these plugins when not in VSCode
  if not is_vscode then
    -- Theme plugins
    local theme_plugins = require("custom.plugins.theme")
    vim.list_extend(plugins, theme_plugins)

    -- Language specific plugins
    local lang_plugins = require("custom.plugins.languages")
    vim.list_extend(plugins, lang_plugins)

    -- Telescope and its extensions
    local telescope_plugins = require("custom.plugins.telescope")
    vim.list_extend(plugins, telescope_plugins)

    -- Utility plugins
    local utility_plugins = require("custom.plugins.utilities")
    vim.list_extend(plugins, utility_plugins)

    -- Core plugins from kickstart
    -- vim.list_extend(plugins, {
    --   { "nvim-treesitter/nvim-treesitter", build = ":TSUpdate" },
    --   { "neovim/nvim-lspconfig" },
    --   { "williamboman/mason.nvim" },
    --   { "williamboman/mason-lspconfig.nvim" },
    --   { "j-hui/fidget.nvim", opts = {} },
    --   { "folke/neodev.nvim" },
    --   { "folke/which-key.nvim", event = "VimEnter" },
    --   { "lewis6991/gitsigns.nvim" },
    --   { "stevearc/conform.nvim" },
    --   { "mfussenegger/nvim-lint" },
    --   { "folke/todo-comments.nvim" },
    --   { "echasnovski/mini.nvim" },
    -- })
  end

  return plugins
end

return load() 