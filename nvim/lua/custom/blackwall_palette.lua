-- blackwall design tokens - generated, do not edit
-- edit theme/blackwall_theme/tokens.py and run `blackwall-theme` instead
-- palette: wallust handoff

---@class BlackwallPalette
return {
  bg        = '#29272B',
  fg        = '#F7F6D9',
  accent    = '#AA9B75',
  on_accent = '#29272B',
  link      = '#70BBD5',
  muted     = '#B1B09E',
  faint     = '#7B7A71',
  cursor    = '#FACDAC',

  -- Surfaces, opaque: a terminal already composites the alpha behind us, so
  -- a translucent highlight group would double up and wash the text out.
  raised    = '#373537',
  raised_hi = '#403E3E',
  sunken    = '#1B191C',
  edge      = '#4A4847',
  selection = '#4D4740',

  warn      = '#E4B363',
  bad       = '#D2696A',
  good      = '#7FB88A',

  ansi = {
    [0] = '#4F4C51',
    [1] = '#AA9B75',
    [2] = '#FDA380',
    [3] = '#F0B864',
    [4] = '#81E0B9',
    [5] = '#DAD1C1',
    [6] = '#E9E692',
    [7] = '#ECEAC0',
    [8] = '#A5A486',
    [9] = '#AA9B75',
    [10] = '#FDA380',
    [11] = '#F0B864',
    [12] = '#81E0B9',
    [13] = '#DAD1C1',
    [14] = '#E9E692',
    [15] = '#ECEAC0',
  },
}
