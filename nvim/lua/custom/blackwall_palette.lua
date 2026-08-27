-- blackwall design tokens - generated, do not edit
-- edit theme/blackwall_theme/tokens.py and run `blackwall-theme` instead
-- palette: wallust handoff

---@class BlackwallPalette
return {
  bg        = '#1B1C22',
  fg        = '#FBF9FA',
  accent    = '#AA9FE3',
  on_accent = '#1B1C22',
  link      = '#70BDF4',
  muted     = '#AFAEB1',
  faint     = '#757478',
  cursor    = '#FCC4FD',

  -- Surfaces, opaque: a terminal already composites the alpha behind us, so
  -- a translucent highlight group would double up and wash the text out.
  raised    = '#2B2B31',
  raised_hi = '#34343A',
  sunken    = '#121216',
  edge      = '#3F3F45',
  selection = '#434158',

  warn      = '#E4B363',
  bad       = '#D2696A',
  good      = '#7FB88A',

  ansi = {
    [0] = '#414349',
    [1] = '#AA9FE3',
    [2] = '#FC8EFF',
    [3] = '#BAD7F7',
    [4] = '#FCD3FB',
    [5] = '#A7F9FF',
    [6] = '#F4EEF2',
    [7] = '#F1EEF0',
    [8] = '#A9A7A8',
    [9] = '#AA9FE3',
    [10] = '#FC8EFF',
    [11] = '#BAD7F7',
    [12] = '#FCD3FB',
    [13] = '#A7F9FF',
    [14] = '#F4EEF2',
    [15] = '#F1EEF0',
  },
}
