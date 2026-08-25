-- blackwall design tokens - generated, do not edit
-- edit theme/blackwall_theme/tokens.py and run `blackwall-theme` instead
-- palette: wallust handoff

---@class BlackwallPalette
return {
  bg        = '#140D1A',
  fg        = '#F5FBFF',
  accent    = '#FB84A2',
  on_accent = '#140D1A',
  link      = '#87B5E1',
  muted     = '#A8AAB1',
  faint     = '#6E6C76',
  cursor    = '#CCD5FF',

  -- Surfaces, opaque: a terminal already composites the alpha behind us, so
  -- a translucent highlight group would double up and wash the text out.
  raised    = '#241E2A',
  raised_hi = '#2D2733',
  sunken    = '#0D0811',
  edge      = '#38333F',
  selection = '#552E40',

  warn      = '#E4B363',
  bad       = '#D2696A',
  good      = '#7FB88A',

  ansi = {
    [0] = '#3C3643',
    [1] = '#FB84A2',
    [2] = '#A3AEFF',
    [3] = '#F999FB',
    [4] = '#78EBFE',
    [5] = '#FBD9FE',
    [6] = '#E3F4FE',
    [7] = '#E9F1F6',
    [8] = '#A3A9AC',
    [9] = '#FB84A2',
    [10] = '#A3AEFF',
    [11] = '#F999FB',
    [12] = '#78EBFE',
    [13] = '#FBD9FE',
    [14] = '#E3F4FE',
    [15] = '#E9F1F6',
  },
}
