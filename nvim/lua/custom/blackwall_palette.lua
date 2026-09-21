-- blackwall design tokens - generated, do not edit
-- edit theme/blackwall_theme/tokens.py and run `blackwall-theme` instead
-- palette: wallust handoff

---@class BlackwallPalette
return {
  bg        = '#101015',
  fg        = '#E5FFFF',
  accent    = '#FE89AA',
  on_accent = '#101015',
  link      = '#88B6E4',
  muted     = '#9DAEAF',
  faint     = '#657073',
  cursor    = '#D3D8D8',

  -- Surfaces, opaque: a terminal already composites the alpha behind us, so
  -- a translucent highlight group would double up and wash the text out.
  raised    = '#1F2125',
  raised_hi = '#272A2F',
  sunken    = '#0A0A0E',
  edge      = '#32363A',
  selection = '#53323F',

  warn      = '#E4B363',
  bad       = '#D2696A',
  good      = '#7FB88A',

  ansi = {
    [0] = '#38393D',
    [1] = '#FE89AA',
    [2] = '#C0B1B1',
    [3] = '#04CFED',
    [4] = '#F7C4FE',
    [5] = '#E3E6FD',
    [6] = '#B6FFFE',
    [7] = '#D2F7F6',
    [8] = '#93ADAC',
    [9] = '#FE89AA',
    [10] = '#C0B1B1',
    [11] = '#04CFED',
    [12] = '#F7C4FE',
    [13] = '#E3E6FD',
    [14] = '#B6FFFE',
    [15] = '#D2F7F6',
  },
}
