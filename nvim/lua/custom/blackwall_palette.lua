-- blackwall design tokens - generated, do not edit
-- edit theme/blackwall_theme/tokens.py and run `blackwall-theme` instead
-- palette: wallust handoff

---@class BlackwallPalette
return {
  bg        = '#1C1500',
  fg        = '#FDF9E1',
  accent    = '#F5E169',
  on_accent = '#1C1500',
  link      = '#85CFD1',
  muted     = '#B0AB94',
  faint     = '#76705A',
  cursor    = '#FAEFAD',

  -- Surfaces, opaque: a terminal already composites the alpha behind us, so
  -- a translucent highlight group would double up and wash the text out.
  raised    = '#2C2510',
  raised_hi = '#352E19',
  sunken    = '#120E00',
  edge      = '#403924',
  selection = '#594E1D',

  warn      = '#E4B363',
  bad       = '#D2696A',
  good      = '#7FB88A',

  ansi = {
    [0] = '#453F2A',
    [1] = '#F5E169',
    [2] = '#F6E479',
    [3] = '#F8E889',
    [4] = '#F9EC98',
    [5] = '#FAEFA8',
    [6] = '#FAEFA8',
    [7] = '#F4EFCB',
    [8] = '#ABA78E',
    [9] = '#F5E169',
    [10] = '#F6E479',
    [11] = '#F8E889',
    [12] = '#F9EC98',
    [13] = '#FAEFA8',
    [14] = '#FAEFA8',
    [15] = '#F4EFCB',
  },
}
