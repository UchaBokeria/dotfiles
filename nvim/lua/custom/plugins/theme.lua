return {
 {
  'xero/evangelion.nvim',
  lazy = false,
  priority = 1000,
  init = function()
   vim.cmd.colorscheme 'evangelion'
  end,
 },

 -- 🗼 TokyoNight
 {
  'folke/tokyonight.nvim',
  priority = 1000,
  config = function()
   vim.cmd.colorscheme 'tokyonight-night'
  end,
 },

 -- ⚡ Fluoromachine
 {
  'maxmx03/fluoromachine.nvim',
  lazy = false,
  priority = 1000,
  config = function()
   local fm = require 'fluoromachine'

   fm.setup {
    glow = true,
    theme = 'fluoromachine',
    transparent = true,
   }

   vim.cmd.colorscheme 'fluoromachine'
  end,
 },
 {
  'diegoulloao/neofusion.nvim',
  priority = 1000,
  config = function()
   require('neofusion').setup()
   vim.cmd.colorscheme 'neofusion'
  end,
 },

 -- 🔷 Poimandres
 {
  'olivercederborg/poimandres.nvim',
  priority = 1000,
  config = function()
   require('poimandres').setup()
   vim.cmd.colorscheme 'poimandres'
  end,
 },

 -- 🌌 Vesper
 {
  'datsfilipe/vesper.nvim',
  priority = 1000,
  config = function()
   vim.cmd.colorscheme 'vesper'
  end,
 },

 -- ❄️ Nord
 {
  'shaunsingh/nord.nvim',
  priority = 1000,
  config = function()
   vim.cmd.colorscheme 'nord'
  end,
 },

 -- 🕶 Cyberpunk (vimscript theme, no config)
 {
  'thedenisnikulin/vim-cyberpunk',
  priority = 1000,
  config = function()
   vim.cmd.colorscheme 'cyberpunk'
  end,
 },

 -- 🦊 Nightfox (includes duskfox, dawnfox, nordfox, etc.)
 {
  'EdenEast/nightfox.nvim',
  priority = 1000,
  config = function()
   require('nightfox').setup {}
   vim.cmd.colorscheme 'nightfox'
  end,
 },

 -- 🎑 Kanagawa
 {
  'rebelot/kanagawa.nvim',
  priority = 1000,
  config = function()
   require('kanagawa').setup {}
   vim.cmd.colorscheme 'kanagawa-wave'
  end,
 },
}

