-- blackwall design tokens - generated, do not edit
-- edit theme/blackwall_theme/tokens.py and run `blackwall-theme` instead
-- palette: wallust handoff

---@class BlackwallPalette
return {
  bg        = '#111211',
  fg        = '#F0F8F7',
  accent    = '#C56B3D',
  on_accent = '#111211',
  link      = '#78AEC5',
  muted     = '#A4AAA9',
  faint     = '#6A6E6D',
  cursor    = '#BCC39A',

  -- Surfaces, opaque: a terminal already composites the alpha behind us, so
  -- a translucent highlight group would double up and wash the text out.
  raised    = '#212221',
  raised_hi = '#2A2B2A',
  sunken    = '#0B0C0B',
  edge      = '#353736',
  selection = '#432B1D',

  warn      = '#E4B363',
  bad       = '#D2696A',
  good      = '#7FB88A',

  ansi = {
    [0] = '#393A39',
    [1] = '#C56B3D',
    [2] = '#888E3D',
    [3] = '#B4ABA9',
    [4] = '#7EB7C0',
    [5] = '#BCBA93',
    [6] = '#D3EBE9',
    [7] = '#E1EDEC',
    [8] = '#9DA6A5',
    [9] = '#C56B3D',
    [10] = '#888E3D',
    [11] = '#B4ABA9',
    [12] = '#7EB7C0',
    [13] = '#BCBA93',
    [14] = '#D3EBE9',
    [15] = '#E1EDEC',
  },
}
