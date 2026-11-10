-- Theme plugins. These only install each scheme and run its setup function.
-- None of them may set a colorscheme: the saved choice is applied in exactly
-- one place, custom.utils.themes, so a restart keeps what <leader>st picked
-- instead of falling through to whichever spec loads last.
return {
 {
  'xero/evangelion.nvim',
  lazy = false,
  priority = 1000,
 },

 -- 🗼 TokyoNight
 {
  'folke/tokyonight.nvim',
  priority = 1000,
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
  end,
 },
 {
  'diegoulloao/neofusion.nvim',
  priority = 1000,
  config = function()
   require('neofusion').setup()
  end,
 },

 -- 🔷 Poimandres
 {
  'olivercederborg/poimandres.nvim',
  priority = 1000,
  config = function()
   require('poimandres').setup()
  end,
 },

 -- 🌌 Vesper
 {
  'datsfilipe/vesper.nvim',
  priority = 1000,
 },

 -- ❄️ Nord
 {
  'shaunsingh/nord.nvim',
  priority = 1000,
 },

 -- 🕶 Cyberpunk (vimscript theme, no config)
 {
  'thedenisnikulin/vim-cyberpunk',
  priority = 1000,
 },

 -- 🦊 Nightfox (includes duskfox, dawnfox, nordfox, etc.)
 {
  'EdenEast/nightfox.nvim',
  priority = 1000,
  config = function()
   require('nightfox').setup {}
  end,
 },

 -- 🎑 Kanagawa
 {
  'rebelot/kanagawa.nvim',
  priority = 1000,
  config = function()
   require('kanagawa').setup {}
  end,
 },
}

