function _G.make_nvim_transparent()
 local groups = {
  -- Main editor
  'Normal',
  'NormalNC',
  'SignColumn',
  'EndOfBuffer',

  -- Floating windows / popups
  'NormalFloat',
  'FloatBorder',

  -- Completion menu
  'Pmenu',
  'PmenuSel',
  'PmenuSbar',
  'PmenuThumb',

  -- Telescope
  'TelescopeNormal',
  'TelescopeBorder',
  'TelescopePromptNormal',
  'TelescopePromptBorder',
  'TelescopeResultsNormal',
  'TelescopeResultsBorder',
  'TelescopePreviewNormal',
  'TelescopePreviewBorder',

  -- Mason
  'MasonNormal',
  'MasonHeader',

  -- LSP
  'LspFloatWinNormal',
  'LspFloatWinBorder',

  -- Misc UI
  'StatusLine',
  'StatusLineNC',
  'LineNr',
  'FoldColumn',
  'WinSeparator',
 }

 for _, group in ipairs(groups) do
  vim.api.nvim_set_hl(0, group, { bg = 'none' })
 end
end

return {}
