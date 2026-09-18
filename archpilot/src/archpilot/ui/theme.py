"""GTK CSS generated from the rice palette, so the window follows wallust.

The token *values* come from the rice's own design system in
`theme/blackwall_theme`, not from a second derivation here. The widget used to
compute its own glass, rim and depth from the same palette with the same
numbers, which meant every change had to be made twice and the two copies were
one edit away from disagreeing forever. This file now owns only the layout -
which token goes where - and the arithmetic lives in one place for the whole
rice.

Three of the rice's rules are spelled out here because this file broke each of
them at some point:

  * type sits on the scale 10 / 11 / 13 / 15 / 24px and in the rice's three
    faces - font_ui for reading, font_mono for things you type or run,
    font_icon ("Symbols Nerd Font") for glyphs;
  * rims are inset rings, not borders. A border adds a pixel to the box and is
    clipped at the rounded corners; a ring is painted inside and follows the
    radius. Where a border became a ring, the padding took the pixel over, so
    nothing moved. The one exception is .attachment, whose thumbnail fills the
    tile and would paint straight over an inset ring;
  * the base colours are the generated tokens' - the contrast-corrected fg and
    accent - not wallust's raw eww/colors.scss pair.

`blackwall_theme` is deliberately pure stdlib, so importing it from archpilot's
venv needs nothing but a path entry.
"""

from __future__ import annotations

import sys

from .. import paths, rofi_theme

_THEME_PKG = paths.DOTFILES / "theme"
if str(_THEME_PKG) not in sys.path:
    sys.path.insert(0, str(_THEME_PKG))

TEMPLATE = """
/* Glass, not paint. Hyprland's blur renders behind any translucent surface, so
   the window is deliberately semi-transparent and depth comes from layering
   alpha - a specular top edge, raised surfaces lit from above, sunken ones
   darker. Emoji reach Noto Color Emoji through fontconfig's fallback. */

window.archpilot {{
  /* Thinner than the panel glass the surfaces inside use. hyprglass bends and
     frosts what is behind this window, and at the panel's 68-74% fill almost
     none of that reached the eye - it read as a dark slab with a rim. */
  background: linear-gradient(158deg, {win_hi} 0%, {win} 45%, {win_lo} 100%);
  color: {fg};
  /* MUST match `rounding` in hypr/configs/archpilot.conf. GTK clips its own
     background and border at this radius while hyprland clips the window at
     its own; when the two disagree the corner arc of the border is cut away
     and the hairline appears to stop short of each corner. */
  border-radius: {r_window};
  /* The rim is an INSET ring, not a border. A real border is drawn at the
     outer edge of the widget, where hyprland's own rounding clips it - which
     is why the hairline used to fade out around each corner while the straight
     runs kept it. An inset shadow is painted inside the clip and follows the
     radius exactly, so the line closes all the way round. */
  border: none;
  /* Inset only. An outer box-shadow on a *top-level* window cannot work: GTK
     paints inside the window's own surface, so a `0 30px 80px` drop has
     nowhere outside to go and is clipped inward - it renders as a dark band
     around the inside of the edge rather than a halo around the outside, and
     it stacked on top of the compositor's shadow besides. The real shadow is
     hyprland's (decoration:shadow in hyprland.conf), which is drawn outside
     the surface where a shadow belongs.

     The rule this follows: an outer shadow belongs on a *child* widget with
     transparent space around it - waybar's capsules, eww's panes - never on
     the window itself. */
  box-shadow:
    inset 0 0 0 1px {rim},
    inset 0 1px 0 {rim_top};
  font-family: {font_ui};
}}

/* #15: more air, and a tighter type scale. */
.ap-root {{ padding: 20px 22px 16px 22px; }}

/* Nothing in this window is keyboard-focusable except the password field, so
   the focus ring is never information - it was drawing a blue box around the
   transcript. */
* {{ outline: none; }}
*:focus, *:focus-visible, label:focus, box:focus, scrolledwindow:focus {{
  outline: none; box-shadow: none; border-color: transparent;
}}

/* ---- chips ---------------------------------------------------------- */
.chip {{
  background: linear-gradient(180deg, {chip_hi}, {chip_lo});
  color: {muted};
  border: none;
  box-shadow: inset 0 0 0 1px {edge};
  border-radius: 999px;
  padding: 5px 14px;
  font-size: 11px;
  font-weight: 700;
  min-height: 0;
}}
.chip:hover {{ background: linear-gradient(180deg, {accent_hi}, {accent_lo});
               color: {fg}; box-shadow: inset 0 0 0 1px {accent_edge}; }}

/* ---- header hierarchy ------------------------------------------------
   The mode chip is the one control with consequences, so it carries weight.
   Engine, model and effort are preferences: joined into one segmented control
   and toned down, so identical pills stop competing for attention. The mode
   states come after the primary rule so they win it. */
.chip.chip-primary {{
  font-size: 13px;
  font-weight: 800;
  padding: 7px 16px;
  box-shadow: inset 0 0 0 1px {edge}, {lift_soft};
}}
.chip.mode-ask    {{ background: linear-gradient(180deg, {accent_hi}, {accent_lo});
                     color: {fg};
                     box-shadow: inset 0 0 0 1px {accent_edge}, {lift_soft}; }}
.chip.mode-action {{ background: linear-gradient(180deg, {warn_hi}, {warn_lo});
                     color: {warn};
                     box-shadow: inset 0 0 0 1px {warn_edge}, {lift_soft}; }}
.engine-group {{
  background: {sunken};
  border: none;
  box-shadow: inset 0 0 0 1px {edge};
  border-radius: 999px;
  padding: 3px;
}}
.chip.chip-quiet {{
  background: transparent;
  box-shadow: none;
  color: {muted};
  font-size: 10px;
  font-weight: 600;
  padding: 4px 11px;
}}
.chip.chip-quiet:hover {{ background: {chip_hi}; color: {fg}; }}

/* Which CLI is answering, readable at a glance without a fourth pill: the
   engine chip leads the group in its own colour and a faint tint of it - the
   accent for Claude, the cooler link colour for Codex. */
.chip.chip-quiet.chip-engine {{ font-weight: 800; }}
.chip.chip-quiet.engine-claude {{ color: {accent}; background: {accent_lo}; }}
.chip.chip-quiet.engine-codex  {{ color: {link}; background: {link_lo}; }}
.chip.chip-quiet.chip-engine:hover {{ background: {chip_hi}; color: {fg}; }}

.vim {{
  border-radius: {r_sm};
  padding: 5px 10px;
  font-size: 10px;
  font-weight: 800;
  font-family: {font_mono};
  background: linear-gradient(180deg, {chip_hi}, {chip_lo});
  border: none;
  box-shadow: inset 0 0 0 1px {edge};
  color: {muted};
}}
.vim.insert {{ background: linear-gradient(180deg, {accent}, {accent_deep});
               color: {on_accent}; box-shadow: inset 0 0 0 1px {accent}; }}
.vim.visual {{ background: linear-gradient(180deg, {warn}, {warn_deep});
               color: {bg}; box-shadow: inset 0 0 0 1px {warn}; }}
.vim.find   {{ background: linear-gradient(180deg, {chip_hi}, {chip_lo});
               color: {accent}; box-shadow: inset 0 0 0 1px {accent_edge}; }}

/* ---- tabs ------------------------------------------------------------ */
/* Hidden until there are two, so a single conversation shows no chrome. */
.tab {{
  background: {chip_lo};
  color: {faint};
  border: none;
  border-radius: {r_md};
  padding: 5px 13px;
  font-size: 11px;
  min-height: 0;
}}
.tab:hover {{ color: {muted}; }}
.tab.on {{
  background: linear-gradient(180deg, {accent_hi}, {accent_lo});
  color: {fg};
  box-shadow: inset 0 0 0 1px {accent_edge};
}}

/* ---- meters --------------------------------------------------------- */
.meter {{
  background: {sunken};
  border: none;
  box-shadow: inset 0 0 0 1px {edge};
  border-radius: {r_md};
  padding: 4px 12px;
}}
.meter-icon  {{ font-family: {font_icon};
                font-size: 11px; color: {faint}; }}
.meter-value {{ font-size: 11px; font-weight: 700; color: {fg}; }}
.meter-note  {{ font-size: 10px; color: {faint}; }}
.meter.warn  {{ background: {warn_lo}; box-shadow: inset 0 0 0 1px {warn_edge}; }}
.meter.warn .meter-value, .meter.warn .meter-note, .meter.warn .meter-icon {{ color: {warn}; }}

progressbar.meter-bar trough {{
  min-height: 5px; min-width: 42px;
  background-color: {sunken_deep}; border-radius: 999px;
}}
progressbar.meter-bar progress {{
  min-height: 5px; border-radius: 999px;
  background: linear-gradient(90deg, {accent}, {accent_deep});
}}
.meter.warn progressbar.meter-bar progress {{ background: {warn}; }}

/* ---- motion ---------------------------------------------------------
   Short and eased: enough to show that something arrived and where it came
   from, never enough to wait for. GTK4 animates opacity and margins, which
   between them give a fade-and-rise. */
@keyframes arrive {{
  from {{ opacity: 0; margin-top: 10px; }}
  to   {{ opacity: 1; margin-top: 0; }}
}}
@keyframes surface {{
  from {{ opacity: 0; margin-bottom: -6px; }}
  to   {{ opacity: 1; margin-bottom: 0; }}
}}
.message.fresh {{ animation: arrive 220ms ease-out; }}
.cmd-panel     {{ animation: surface 180ms ease-out; }}
.panel.notice  {{ animation: surface 200ms ease-out; }}
.attachments   {{ animation: surface 180ms ease-out; }}

/* ---- chat ----------------------------------------------------------- */
.chat {{ background: transparent; }}

/* Each answer is its own pane of glass, lit from the top-left. */
.bubble {{
  background: linear-gradient(160deg, {bubble_hi}, {bubble_lo});
  border: none;
  border-radius: {r_lg};
  padding: 15px 17px;
  box-shadow: inset 0 0 0 1px {edge}, {lift_soft};
  transition: box-shadow 180ms ease;
}}
.bubble.streaming {{ box-shadow: inset 0 0 0 1px {accent_edge}, {lift_soft}; }}

.asked {{
  font-size: 11px;
  color: {faint};
  font-family: {font_mono};
  padding-left: 3px;
}}
.answer {{ font-size: 13px; color: {fg}; }}
/* Links look like links, and stay legible on glass. */
.answer a, .asked a {{
  color: {link};
  text-decoration: underline;
  text-decoration-color: {link_edge};
}}
.answer a:hover, .asked a:hover {{ text-decoration-color: {link}; }}
.bubble > label {{ padding-bottom: 1px; }}

/* A command that has already run: kept as a record, no longer pressable. */
.ran {{
  font-family: {font_mono};
  font-size: 11px;
  color: {faint};
  padding: 5px 2px 0 2px;
}}

selection, *:selected {{ background-color: {accent_lo}; color: {fg}; }}

/* A message the keyboard is aimed at.

   The old version tinted the row background, which on a dark theme was almost
   the same colour as the background it sat on - so the only real signal was a
   thin border of the same hue as the streaming border, and it read as an
   artefact rather than a selection. Now the CONTENT itself is ringed in the
   accent and lifted off the glass, with no row tint competing behind it. */
.message {{ padding: 1px 2px; border-radius: {r_lg}; }}
.message.chosen .bubble {{
  background: linear-gradient(160deg, {chosen_hi}, {chosen_lo});
  box-shadow: inset 0 0 0 1.5px {accent}, inset 0 1px 0 {chosen_sheen};
}}
.message.chosen .asked {{ color: {accent}; }}
/* A selected message that is also streaming keeps the selection ring: which
   message the keys will act on matters more than which one is still typing. */
.message.chosen .bubble.streaming {{
  box-shadow: inset 0 0 0 1.5px {accent}, inset 0 1px 0 {chosen_sheen};
}}

/* How long the answer took, as Claude Code shows it. */
.took {{ font-size: 10px; color: {faint};
         font-family: {font_mono}; padding-top: 2px; }}

.toast {{
  font-size: 10px;
  color: {accent};
  background: {accent_lo};
  border-radius: 999px;
  padding: 2px 10px;
}}

.search-field {{
  background: {sunken};
  border: none;
  box-shadow: inset 0 0 0 1px {accent_edge};
  border-radius: {r_md};
  padding: 11px 15px;
  font-family: {font_mono};
  font-size: 13px;
}}

.icon-btn.done {{ color: {accent}; box-shadow: inset 0 0 0 1px {accent_edge}; }}

/* ---- prompt --------------------------------------------------------- */
/* Inset: the one surface you type into reads as a well in the glass rather
   than another floating card. Same size as the answers it produces. */
.prompt {{
  background: {sunken};
  border: none;
  border-radius: {r_lg};
  /* Tight when empty: an idle prompt should read as one line, not a panel. */
  padding: 10px 14px;
  min-height: 0;
  font-family: {font_mono};
  font-size: 13px;
  box-shadow: inset 0 0 0 1px {edge}, {lift};
  transition: box-shadow 200ms ease, background-color 200ms ease;
}}
/* Typing lifts it further still, so the thing you are acting on is plainly
   the thing in front. */
.prompt.insert {{
  background: {sunken_deep};
  box-shadow: inset 0 0 0 1px {accent_edge}, {lift_high};
}}

.status {{ font-size: 11px; color: {muted}; }}
.hint   {{ font-size: 10px; color: {faint};
           font-family: {font_mono}; }}

/* ---- actions -------------------------------------------------------- */
.action {{
  background: linear-gradient(180deg, {accent_hi}, {accent_lo});
  border: none;
  box-shadow: inset 0 0 0 1px {accent_edge};
  border-radius: {r_md};
  padding: 10px 14px;
  font-family: {font_mono};
  font-size: 13px;
  color: {fg};
}}
.action:hover {{ background: linear-gradient(180deg, {accent}, {accent_lo}); }}

/* Every icon button carries a Nerd Font glyph, so it takes the icon face -
   any other family draws a different symbol at the same codepoint. */
.icon-btn {{
  background: linear-gradient(180deg, {chip_hi}, {chip_lo});
  border: none;
  box-shadow: inset 0 0 0 1px {edge};
  border-radius: {r_md};
  padding: 7px 11px;
  font-family: {font_icon};
  font-size: 13px;
  color: {muted};
  min-height: 0;
}}
.icon-btn:hover {{ background: linear-gradient(180deg, {accent_hi}, {accent_lo});
                   color: {fg}; box-shadow: inset 0 0 0 1px {accent_edge}; }}

/* ---- panels --------------------------------------------------------- */
.panel {{
  background: linear-gradient(180deg, {warn_hi}, {warn_lo});
  border: none;
  border-radius: {r_lg};
  padding: 14px;
  box-shadow: inset 0 0 0 1px {warn_edge}, {lift};
}}
.panel.danger {{ background: linear-gradient(180deg, {bad_hi}, {bad_lo});
                 box-shadow: inset 0 0 0 1px {bad_edge}, {lift}; }}
.panel-title {{ font-size: 11px; font-weight: 800; color: {warn}; }}
.panel.danger .panel-title {{ color: {bad}; }}

/* A recognised, fixable failure. Warmer and brighter than .panel so it reads
   as "here is what to do", not as the red .error line's sibling. */
.panel.notice {{
  background: linear-gradient(155deg, {notice_hi}, {notice_lo});
  box-shadow: inset 0 0 0 1px {notice_edge}, inset 0 1px 0 {notice_sheen};
}}
.panel.notice .panel-title {{ font-size: 13px; color: {warn}; }}
.panel.notice .small {{ color: {notice_text}; }}
/* ---- tabs, attachments ---------------------------------------------- */
/* The holder is the tab: it carries the surface, and the label and the close
   x sit inside it, both flat. Styling the label as the tab left the x
   floating outside the thing it belonged to. */
.tab-holder {{
  background: {chip_lo};
  border: none;
  box-shadow: inset 0 0 0 1px {edge};
  border-radius: 999px;
  padding: 1px 6px 1px 3px;
  transition: background-color 180ms ease, box-shadow 180ms ease;
}}
.tab-holder:hover {{ background: {chip_hi}; }}
.tab-holder.on {{
  background: linear-gradient(180deg, {accent_hi}, {accent_lo});
  box-shadow: inset 0 0 0 1px {accent_edge}, {lift_soft};
}}
.tab-holder .tab {{
  background: transparent;
  border: none;
  box-shadow: none;
  padding: 4px 12px;
}}
.tab-holder.on .tab {{ color: {accent}; font-weight: 700; }}

.tab-close {{
  font-family: {font_mono};
  font-size: 11px;
  font-weight: 700;
  color: {faint};
  background: transparent;
  border: none;
  /* Symmetric on every side, so the glyph lands in the middle of the round
     hover background. Any asymmetry here shows up as an off-centre x. */
  padding: 0;
  margin: 0 2px;
  min-height: 17px;
  min-width: 17px;
  border-radius: 999px;
  transition: background-color 150ms ease, color 150ms ease;
}}
.tab-close:hover, .tab-close.forced-hover {{ background: {bad}; color: {bg}; }}
.tab-holder.on .tab-close {{ color: {accent}; }}
.tab-holder.on .tab-close:hover {{ background: {bad}; color: {bg}; }}

/* Waiting for the first token. */
.typing {{ padding: 3px 1px; }}
.typing-dot {{
  font-size: 15px;
  color: {faint};
  opacity: 0.35;
  transition: opacity 220ms ease, color 220ms ease;
}}
.typing-dot.lit {{ color: {accent}; opacity: 1; }}
/* Names the tool being run, so a long wait reads as progress. */
.typing-note {{ font-size: 11px; color: {muted}; padding-left: 6px; }}

/* A chat the user has named. */
.hit-named {{ color: {accent}; font-weight: 600; }}
.rename {{
  background: {sunken_deep};
  border: none;
  box-shadow: inset 0 0 0 1px {accent_edge};
  border-radius: {r_md};
  padding: 4px 9px;
  font-size: 13px;
  color: {fg};
  min-height: 0;
}}
.rename:focus {{ box-shadow: inset 0 0 0 1px {accent}; }}

/* The `:` suggestion list and the help sheet. */
.cmd-panel {{
  background: linear-gradient(160deg, {chosen_hi}, {bubble_lo});
  border: none;
  border-radius: {r_lg};
  padding: 8px;
  box-shadow: inset 0 0 0 1px {accent_edge}, {lift_high};
}}
.cmd-row {{
  background: transparent;
  border: none;
  border-radius: {r_md};
  padding: 5px 9px;
  min-height: 0;
}}
.cmd-row:hover {{ background: {accent_lo}; }}
.cmd-row.on {{
  background: linear-gradient(160deg, {chosen_hi}, {chosen_lo});
  box-shadow: inset 0 0 0 1px {accent};
}}
.cmd-static {{ padding: 3px 9px; }}
.cmd-name {{ font-family: {font_mono};
             font-size: 11px; font-weight: 700; color: {accent}; }}
.cmd-key  {{ font-family: {font_mono};
             font-size: 11px; font-weight: 700; color: {fg}; }}
.cmd-help {{ font-size: 11px; color: {muted}; }}
.cmd-group {{
  font-size: 10px; font-weight: 800; color: {faint};
  padding: 9px 9px 3px 9px;
}}

.attachments {{ padding: 3px 2px 0 2px; }}
/* A real border, deliberately: the thumbnail fills the tile and would paint
   over an inset ring. */
.attachment {{
  background: linear-gradient(160deg, {bubble_hi}, {bubble_lo});
  border: 1px solid {edge};
  border-radius: {r_md};
}}
.attachment-thumb {{ border-radius: {r_md}; }}
.attachment-kind {{
  font-family: {font_mono};
  font-size: 10px; font-weight: 800; color: {muted};
}}
.attachment {{ transition: border-color 180ms ease, box-shadow 180ms ease; }}
.attachment.hovered {{ border: 1px solid {accent_edge}; box-shadow: {lift}; }}

/* Faint until the pointer is on the tile, then solid.

   Not fully hidden: hover is the nicer idea, but if the pointer-enter event
   never arrives - and it does not, for instance, when the compositor warps the
   cursor rather than moving it - an invisible control leaves no way at all to
   remove an attachment. A faint badge is still quiet, and it can never
   strand you. */
.attachment-drop {{
  font-family: {font_mono};
  font-size: 10px;
  color: {fg};
  background: {scrim};
  border: none;
  box-shadow: inset 0 0 0 1px {edge};
  padding: 2px 5px;
  margin: 3px;
  min-height: 0;
  min-width: 0;
  border-radius: 999px;
  opacity: 0.3;
  transition: opacity 160ms ease, background-color 160ms ease;
}}
.attachment.hovered .attachment-drop {{ opacity: 1; }}
.attachment-drop:hover {{ background: {bad}; color: {bg}; opacity: 1; }}

/* Which half the keyboard is aimed at. Without this, tabbing to an empty
   chat changed nothing on screen.

   A rail down the leading edge, not a tint: filling the transcript with
   colour drowns out the selected message's own ring, which is the thing you
   actually need to see. The marker should say "keys land here", quietly. */
.chat.region-active {{
  border-left: 2px solid {accent};
  padding-left: 9px;
}}
.chat {{
  border-left: 2px solid transparent;
  padding-left: 9px;
  transition: border-color 200ms ease;
}}

/* Floats inside the input, bottom right. Small and quiet: it is a hint
   about what you are halfway through typing, not a control. */
.pending-keys {{
  font-family: {font_mono};
  font-size: 10px;
  font-weight: 700;
  color: {accent};
  background: {accent_lo};
  border: none;
  box-shadow: inset 0 0 0 1px {accent_edge};
  border-radius: {r_sm};
  padding: 2px 7px;
  margin: 0 9px 6px 0;
}}
.notice-icon {{ font-family: {font_icon}; font-size: 15px; color: {warn}; }}
.notice-fix, .notice-retry {{
  background: linear-gradient(180deg, {warn_hi}, {warn_lo});
  border: none;
  box-shadow: inset 0 0 0 1px {warn_edge};
  border-radius: {r_md};
  padding: 5px 13px;
  font-size: 11px;
  font-weight: 700;
  color: {warn};
  min-height: 0;
}}
.notice-fix:hover, .notice-retry:hover {{
  background: linear-gradient(180deg, {warn}, {warn_deep});
  color: {bg};
}}
.mono  {{ font-family: {font_mono}; font-size: 13px; color: {fg}; }}
.small {{ font-size: 11px; color: {muted}; }}
.error {{ font-size: 13px; color: {bad}; }}

.secret {{
  background: {sunken_deep};
  border: none;
  box-shadow: inset 0 0 0 1px {bad_edge};
  border-radius: {r_md};
  padding: 10px 12px;
  font-family: {font_mono};
  font-size: 13px;
  color: {fg};
}}

/* ---- history -------------------------------------------------------- */
/* The selected row is ringed rather than bordered, so choosing one no longer
   nudges its text by a pixel. */
.hit {{ border-radius: {r_md}; padding: 8px 12px; font-size: 13px; color: {muted}; }}
.hit.on {{ background: linear-gradient(180deg, {accent_hi}, {accent_lo});
           color: {fg}; box-shadow: inset 0 0 0 1px {accent_edge}; }}
.hit-meta {{ font-size: 10px; color: {faint};
             font-family: {font_mono}; }}

/* Thin, transparent, and dimmed until you actually reach for it. The stock
   GTK scrollbar is a solid grey trough that cuts straight through the glass. */
scrollbar {{
  background: transparent;
  border: none;
  padding: 0;
  margin: 0;
  transition: opacity 260ms ease;
  opacity: 0.32;
}}
scrollbar:hover {{ opacity: 1; }}
scrollbar trough {{ background: transparent; border: none; }}
scrollbar slider {{
  background-color: {faint};
  border: none;
  border-radius: 999px;
  min-width: 5px;
  min-height: 26px;
  margin: 2px;
  transition: background-color 200ms ease;
}}
scrollbar slider:hover {{ background-color: {muted}; }}
"""

#: The rice's three faces, as theme/blackwall_theme/tokens.py defines them.
#: Only used when that package cannot be imported; normally they come from it.
FONT_UI = ('"Inter", "SF Pro Text", "Noto Sans", '
           '"JetBrainsMono Nerd Font", "Symbols Nerd Font", sans-serif')
FONT_MONO = '"JetBrainsMono Nerd Font", "MesloLGS NF", monospace'
FONT_ICON = '"Symbols Nerd Font"'


def theme_source():
    """The file wallust rewrites; watching it is what makes re-theming live."""
    return rofi_theme.COLORS_SCSS


def _alpha(hex_colour: str, pct: int) -> str:
    value = hex_colour.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{pct / 100:.2f})"


def _shared_tokens():
    """The rice's design tokens, or None if the shared package is unavailable.

    A missing or broken theme package must not stop the widget from rendering -
    it would leave the user with no way to ask what went wrong - so the local
    derivation below stays as a fallback.
    """
    try:
        from blackwall_theme.palette import load
        from blackwall_theme.tokens import build
        return build(load())
    except Exception:
        return None


def css() -> str:
    shared = _shared_tokens()
    if shared is not None:
        # The tokens carry the rice's CORRECTED colours - fg lifted to 7:1
        # against bg, a colourless accent replaced - where eww/colors.scss holds
        # wallust's raw pair. Deriving from the raw pair is how this window
        # drifted off-key from every other panel.
        bg, fg, accent = shared.bg.hex6, shared.fg.hex6, shared.accent.hex6
        warn, bad = shared.warn.hex6, shared.bad.hex6
    else:
        colours = rofi_theme._read_colors()
        bg, fg, accent = colours["bg"], colours["fg"], colours["accent"]
        warn, bad = "#E4B363", "#D2696A"
    deep = rofi_theme._mix(accent, bg, 0.35)
    # A cooler second accent, for things that are informational rather than
    # active: links, mostly. One accent doing every job - mode chip, selection,
    # links, pending keys, command names - meant none of them read as special.
    link = rofi_theme._mix(accent, "#5AC8FA", 0.72)
    local = _local_tokens(bg, fg, accent, warn, bad, deep, link)
    if shared is not None:
        local.update(_from_shared(shared))
    return TEMPLATE.format(**local)


def _from_shared(t) -> dict:
    """Map the rice's tokens onto the names this stylesheet uses."""
    return {
        "glass_hi": t.glass_hi.css, "glass": t.glass.css, "glass_lo": t.glass_lo.css,
        # The window's own fill: the same three stops, thinned so the glass
        # behind it is visible through the panel.
        "win_hi": t.glass_hi.alpha(44).css, "win": t.bg.alpha(38).css,
        "win_lo": t.glass_lo.alpha(46).css,
        "rim": t.rim.css, "rim_top": t.rim_top.css, "rim_bottom": t.rim_bottom.css,
        "edge": t.edge.css,
        "muted": t.muted.css, "faint": t.faint.css,
        "on_accent": t.on_accent.hex6,
        "chip_hi": t.raised_hi.css, "chip_lo": t.raised_lo.css,
        "sunken": t.sunken.css, "sunken_deep": t.sunken_deep.css,
        "accent_hi": t.accent_hi.css, "accent_lo": t.accent_lo.css,
        "accent_edge": t.accent_edge.css, "accent_deep": t.accent_deep.hex6,
        "link": t.link.hex6, "link_edge": t.link_edge.css,
        "link_lo": t.link.alpha(14).css,
        "warn_hi": t.warn_hi.css, "warn_edge": t.warn_edge.css,
        "bad_hi": t.bad_hi.css, "bad_edge": t.bad_edge.css,
        "lift_soft": t.lift_soft, "lift": t.lift, "lift_high": t.lift_high,
        "r_window": t.r_window, "r_lg": t.r_lg, "r_md": t.r_md, "r_sm": t.r_sm,
        "font_ui": t.font_ui, "font_mono": t.font_mono, "font_icon": t.font_icon,
    }


def _local_tokens(bg, fg, accent, warn, bad, deep, link) -> dict:
    return dict(
        bg=bg, fg=fg, accent=accent, warn=warn, bad=bad,
        accent_deep=deep,
        on_accent=rofi_theme.on_accent(bg, fg, accent),
        link=link,
        link_edge=_alpha(link, 55),
        link_lo=_alpha(link, 14),

        font_ui=FONT_UI,
        font_mono=FONT_MONO,
        font_icon=FONT_ICON,

        # -- radii ------------------------------------------------------
        # Three sizes, not twelve. Anything that looked "about 12px" now picks
        # the nearest of these, which is most of what makes a set of panels
        # look like one designed thing rather than several.
        r_lg="18px",      # panes: bubbles, panels, the window's own children
        r_md="12px",      # controls: chips, tabs, tiles
        r_sm="8px",       # small marks: close buttons, key hints

        # -- depth ------------------------------------------------------
        # Real glass stacks. The transcript sits back, the input and any open
        # panel come forward. Shadows do the work; opacity would grey the text.
        lift_soft="0 1px 3px rgba(0,0,0,0.18)",
        lift="0 4px 14px rgba(0,0,0,0.28)",
        lift_high="0 10px 30px rgba(0,0,0,0.38)",
        warn_deep=rofi_theme._mix(warn, bg, 0.35),
        # The window itself: translucent so the compositor's blur shows
        # through. hyprland blurs anything with alpha (size 15, passes 3), so
        # the lower these are the more the glass actually reads as glass. Text
        # stays fully opaque because the alpha is on the BACKGROUND, not on the
        # window - a hyprland `opacity` rule would fade the type as well.
        # Tuned against a busy wallpaper: much below this and the footer hint
        # stops being readable over whatever happens to be behind the window.
        glass_hi=_alpha(rofi_theme._mix(bg, fg, 0.13), 72),
        glass=_alpha(bg, 68),
        glass_lo=_alpha(rofi_theme._mix(bg, "#000000", 0.30), 74),
        win_hi=_alpha(rofi_theme._mix(bg, fg, 0.13), 44),
        win=_alpha(bg, 38),
        win_lo=_alpha(rofi_theme._mix(bg, "#000000", 0.30), 46),
        #: The window's own rim. Must equal `rounding` in archpilot.conf.
        r_window="22px",
        rim=_alpha("#FFFFFF", 16),
        rim_top=_alpha("#FFFFFF", 20),
        rim_bottom=_alpha("#000000", 26),
        edge=_alpha(fg, 13),
        # Raised surfaces get a top-light gradient, sunken ones go darker.
        chip_hi=_alpha(fg, 11),
        chip_lo=_alpha(fg, 5),
        sunken=_alpha("#000000", 22),
        sunken_deep=_alpha("#000000", 34),
        accent_hi=_alpha(accent, 30),
        accent_lo=_alpha(accent, 16),
        accent_edge=_alpha(accent, 48),
        chosen_sheen=_alpha("#FFFFFF", 13),
        # A dark scrim, so a control sitting on top of an image stays
        # readable whatever the image happens to be.
        scrim=_alpha("#000000", 62),
        notice_hi=_alpha(warn, 30),
        notice_lo=_alpha(warn, 13),
        notice_edge=_alpha(warn, 62),
        notice_sheen=_alpha("#FFFFFF", 16),
        notice_text=rofi_theme._mix(warn, fg, 0.55),
        warn_hi=_alpha(warn, 22),
        warn_lo=_alpha(warn, 11),
        warn_edge=_alpha(warn, 45),
        bad_hi=_alpha(bad, 20),
        bad_lo=_alpha(bad, 10),
        bad_edge=_alpha(bad, 45),
        bubble_hi=_alpha(fg, 8),
        bubble_lo=_alpha(fg, 3),
        chosen_hi=_alpha(accent, 20),
        chosen_lo=_alpha(accent, 8),
        muted=_alpha(fg, 66),
        faint=_alpha(fg, 40),
    )
