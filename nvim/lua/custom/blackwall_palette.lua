-- blackwall design tokens - generated, do not edit
-- edit theme/blackwall_theme/tokens.py and run `blackwall-theme` instead
-- palette: wallust handoff

---@class BlackwallPalette
return {
  bg        = '#1C1D24',
  fg        = '#FEF5FD',
  accent    = '#EC71F5',
  on_accent = '#1C1D24',
  link      = '#83B0F9',
  muted     = '#B1ACB3',
  faint     = '#76737B',
  cursor    = '#D4C9DA',

  -- Surfaces, opaque: a terminal already composites the alpha behind us, so
  -- a translucent highlight group would double up and wash the text out.
  raised    = '#2C2C33',
  raised_hi = '#35353C',
  sunken    = '#121317',
  edge      = '#404047',
  selection = '#56355F',

  warn      = '#E4B363',
  bad       = '#D2696A',
  good      = '#7FB88A',

  ansi = {
    [0] = '#42444B',
    [1] = '#EC71F5',
    [2] = '#AA9EB7',
    [3] = '#56B6E5',
    [4] = '#70E7ED',
    [5] = '#D3E2F7',
    [6] = '#FBE1FA',
    [7] = '#F5E8F4',
    [8] = '#ABA2AB',
    [9] = '#EC71F5',
    [10] = '#AA9EB7',
    [11] = '#56B6E5',
    [12] = '#70E7ED',
    [13] = '#D3E2F7',
    [14] = '#FBE1FA',
    [15] = '#F5E8F4',
  },
}
