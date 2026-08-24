"""GTK CSS generated from the rice palette, so the window follows wallust."""

from __future__ import annotations

from .. import rofi_theme

TEMPLATE = """
/* Glass, not paint. Hyprland's blur renders behind any translucent surface, so
   the window is deliberately semi-transparent and depth comes from layering
   alpha - a specular top edge, raised surfaces lit from above, sunken ones
   darker. Emoji fall back to Noto Color Emoji via the font stack. */

window.archpilot {{
  background: linear-gradient(158deg, {glass_hi} 0%, {glass} 45%, {glass_lo} 100%);
  color: {fg};
  border-radius: {r_lg};
  border: 1px solid {edge};
  box-shadow: 0 28px 70px rgba(0,0,0,0.55);
  font-family: "Inter", "SF Pro Text", "JetBrainsMono Nerd Font", "Noto Color Emoji", sans-serif;
}}

/* #15: more air, and a tighter type scale - 10/11/13 only. */
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
  border: 1px solid {edge};
  border-radius: 999px;
  padding: 4px 13px;
  font-size: 11px;
  font-weight: 700;
  min-height: 0;
}}
.chip:hover {{ background: linear-gradient(180deg, {accent_hi}, {accent_lo});
               color: {fg}; border: 1px solid {accent_edge}; }}
.chip.mode-ask    {{ background: linear-gradient(180deg, {accent_hi}, {accent_lo});
                     color: {fg}; border: 1px solid {accent_edge}; }}
.chip.mode-action {{ background: linear-gradient(180deg, {warn_hi}, {warn_lo});
                     color: {warn}; border: 1px solid {warn_edge}; }}

.vim {{
  border-radius: {r_sm};
  padding: 4px 9px;
  font-size: 10px;
  font-weight: 800;
  font-family: "JetBrainsMonoNL Nerd Font", monospace;
  background: linear-gradient(180deg, {chip_hi}, {chip_lo});
  border: 1px solid {edge};
  color: {muted};
}}
.vim.insert {{ background: linear-gradient(180deg, {accent}, {accent_deep});
               color: {bg}; border: 1px solid {accent}; }}
.vim.visual {{ background: linear-gradient(180deg, {warn}, {warn_deep});
               color: {bg}; border: 1px solid {warn}; }}
.vim.find   {{ background: linear-gradient(180deg, {chip_hi}, {chip_lo});
               color: {accent}; border: 1px solid {accent_edge}; }}

/* ---- tabs ------------------------------------------------------------ */
/* Hidden until there are two, so a single conversation shows no chrome. */
.tab {{
  background: {chip_lo};
  color: {faint};
  border: 1px solid transparent;
  border-radius: {r_md};
  padding: 4px 12px;
  font-size: 11px;
  min-height: 0;
}}
.tab:hover {{ color: {muted}; }}
.tab.on {{
  background: linear-gradient(180deg, {accent_hi}, {accent_lo});
  color: {fg};
  border: 1px solid {accent_edge};
}}

/* ---- meters --------------------------------------------------------- */
.meter {{
  background: {sunken};
  border: 1px solid {edge};
  border-radius: {r_md};
  padding: 3px 11px;
}}
.meter-icon  {{ font-family: "JetBrainsMonoNL Nerd Font", monospace;
                font-size: 11px; color: {faint}; }}
.meter-value {{ font-size: 11px; font-weight: 700; color: {fg}; }}
.meter-note  {{ font-size: 10px; color: {faint}; }}
.meter.warn  {{ background: {warn_lo}; border: 1px solid {warn_edge}; }}
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
  border: 1px solid {edge};
  border-radius: {r_lg};
  padding: 14px 16px;
  box-shadow: {lift_soft};
  transition: box-shadow 180ms ease, border-color 180ms ease;
}}
.bubble.streaming {{ border: 1px solid {accent_edge}; }}

.asked {{
  font-size: 12px;
  color: {faint};
  font-family: "JetBrainsMonoNL Nerd Font", monospace;
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
  font-family: "JetBrainsMono Nerd Font", monospace;
  font-size: 12px;
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
  border: 1.5px solid {accent};
  box-shadow: inset 0 1px 0 {chosen_sheen};
}}
.message.chosen .asked {{ color: {accent}; }}
/* A selected message that is also streaming keeps the selection ring: which
   message the keys will act on matters more than which one is still typing. */
.message.chosen .bubble.streaming {{ border: 1.5px solid {accent}; }}

/* How long the answer took, as Claude Code shows it. */
.took {{ font-size: 10px; color: {faint};
         font-family: "JetBrainsMonoNL Nerd Font", monospace; padding-top: 2px; }}

.toast {{
  font-size: 10px;
  color: {accent};
  background: {accent_lo};
  border-radius: 999px;
  padding: 2px 10px;
}}

.search-field {{
  background: {sunken};
  border: 1px solid {accent_edge};
  border-radius: {r_md};
  padding: 10px 14px;
  font-family: "JetBrainsMono Nerd Font", monospace;
  font-size: 13px;
}}

.icon-btn.done {{ color: {accent}; border: 1px solid {accent_edge}; }}

/* ---- prompt --------------------------------------------------------- */
/* Inset: the one surface you type into reads as a well in the glass rather
   than another floating card. */
.prompt {{
  background: {sunken};
  border: 1px solid {edge};
  border-radius: {r_lg};
  /* Tight when empty: an idle prompt should read as one line, not a panel. */
  padding: 9px 13px;
  min-height: 0;
  font-family: "JetBrainsMono Nerd Font", "Noto Color Emoji", monospace;
  font-size: 14px;
}}
.prompt {{
  box-shadow: {lift};
  transition: border-color 200ms ease, box-shadow 200ms ease,
              background-color 200ms ease;
}}
/* Typing lifts it further still, so the thing you are acting on is plainly
   the thing in front. */
.prompt.insert {{
  border: 1px solid {accent_edge};
  background: {sunken_deep};
  box-shadow: {lift_high};
}}

.status {{ font-size: 11px; color: {muted}; }}
.hint   {{ font-size: 10px; color: {faint};
           font-family: "JetBrainsMonoNL Nerd Font", monospace; }}

/* ---- actions -------------------------------------------------------- */
.action {{
  background: linear-gradient(180deg, {accent_hi}, {accent_lo});
  border: 1px solid {accent_edge};
  border-radius: {r_md};
  padding: 9px 13px;
  font-family: "JetBrainsMono Nerd Font", monospace;
  font-size: 12px;
  color: {fg};
}}
.action:hover {{ background: linear-gradient(180deg, {accent}, {accent_lo}); }}

.icon-btn {{
  background: linear-gradient(180deg, {chip_hi}, {chip_lo});
  border: 1px solid {edge};
  border-radius: {r_md};
  padding: 6px 10px;
  font-family: "JetBrainsMonoNL Nerd Font", monospace;
  font-size: 12px;
  color: {muted};
  min-height: 0;
}}
.icon-btn:hover {{ background: linear-gradient(180deg, {accent_hi}, {accent_lo});
                   color: {fg}; border: 1px solid {accent_edge}; }}

/* ---- panels --------------------------------------------------------- */
.panel {{
  background: linear-gradient(180deg, {warn_hi}, {warn_lo});
  border: 1px solid {warn_edge};
  border-radius: {r_lg};
  padding: 13px;
  box-shadow: {lift};
}}
.panel.danger {{ background: linear-gradient(180deg, {bad_hi}, {bad_lo});
                 border: 1px solid {bad_edge}; }}
.panel-title {{ font-size: 11px; font-weight: 800; color: {warn}; }}
.panel.danger .panel-title {{ color: {bad}; }}

/* A recognised, fixable failure. Warmer and brighter than .panel so it reads
   as "here is what to do", not as the red .error line's sibling. */
.panel.notice {{
  background: linear-gradient(155deg, {notice_hi}, {notice_lo});
  border: 1px solid {notice_edge};
  box-shadow: inset 0 1px 0 {notice_sheen};
}}
.panel.notice .panel-title {{ font-size: 13px; color: {warn}; }}
.panel.notice .small {{ color: {notice_text}; }}
/* ---- tabs, attachments ---------------------------------------------- */
/* The holder is the tab: it carries the surface, and the label and the close
   x sit inside it, both flat. Styling the label as the tab left the x
   floating outside the thing it belonged to. */
.tab-holder {{
  background: {chip_lo};
  border: 1px solid {edge};
  border-radius: 999px;
  padding: 0 5px 0 2px;
  transition: background-color 180ms ease, border-color 180ms ease;
}}
.tab-holder:hover {{ background: {chip_hi}; }}
.tab-holder.on {{
  background: linear-gradient(180deg, {accent_hi}, {accent_lo});
  border: 1px solid {accent_edge};
  box-shadow: {lift_soft};
}}
.tab-holder .tab {{
  background: transparent;
  border: none;
  box-shadow: none;
}}
.tab-holder.on .tab {{ color: {accent}; font-weight: 700; }}

.tab-close {{
  font-family: "JetBrainsMono Nerd Font", monospace;
  font-size: 8px;
  color: {faint};
  background: transparent;
  border: none;
  /* No vertical padding and a round hit area: padding made the button as tall
     as the tab, so hovering lit a slab the full height of the pill. */
  padding: 0;
  margin: 0 1px 0 3px;
  min-height: 16px;
  min-width: 16px;
  border-radius: 999px;
  transition: background-color 150ms ease, color 150ms ease;
}}
.tab-close:hover {{ background: {bad}; color: {bg}; }}
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
  border: 1px solid {accent_edge};
  border-radius: {r_md};
  padding: 3px 8px;
  font-size: 12px;
  color: {fg};
  min-height: 0;
}}
.rename:focus {{ border: 1px solid {accent}; }}

/* The `:` suggestion list and the help sheet. */
.cmd-panel {{
  background: linear-gradient(160deg, {chosen_hi}, {bubble_lo});
  border: 1px solid {accent_edge};
  border-radius: {r_lg};
  padding: 7px;
  box-shadow: {lift_high};
}}
.cmd-row {{
  background: transparent;
  border: 1px solid transparent;
  border-radius: {r_md};
  padding: 4px 8px;
  min-height: 0;
}}
.cmd-row:hover {{ background: {accent_lo}; }}
.cmd-row.on {{
  background: linear-gradient(160deg, {chosen_hi}, {chosen_lo});
  border: 1px solid {accent};
}}
.cmd-static {{ padding: 3px 9px; }}
.cmd-name {{ font-family: "JetBrainsMono Nerd Font", monospace;
             font-size: 12px; font-weight: 700; color: {accent}; }}
.cmd-key  {{ font-family: "JetBrainsMono Nerd Font", monospace;
             font-size: 11px; font-weight: 700; color: {fg}; }}
.cmd-help {{ font-size: 11px; color: {muted}; }}
.cmd-group {{
  font-size: 10px; font-weight: 800; color: {faint};
  padding: 9px 9px 3px 9px;
}}

.attachments {{ padding: 3px 2px 0 2px; }}
.attachment {{
  background: linear-gradient(160deg, {bubble_hi}, {bubble_lo});
  border: 1px solid {edge};
  border-radius: {r_md};
}}
.attachment-thumb {{ border-radius: {r_md}; }}
.attachment-kind {{
  font-family: "JetBrainsMono Nerd Font", monospace;
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
  font-family: "JetBrainsMono Nerd Font", monospace;
  font-size: 9px;
  color: {fg};
  background: {scrim};
  border: 1px solid {edge};
  padding: 1px 4px;
  margin: 3px;
  min-height: 0;
  min-width: 0;
  border-radius: 999px;
  opacity: 0.3;
  transition: opacity 160ms ease, background-color 160ms ease;
}}
.attachment.hovered .attachment-drop {{ opacity: 1; }}
.attachment-drop:hover {{ background: {bad}; color: {bg}; opacity: 1; }}

/* Floats inside the input, bottom right. Small and quiet: it is a hint
   about what you are halfway through typing, not a control. */
/* ---- header hierarchy ------------------------------------------------
   The mode chip is the one control with consequences, so it carries weight.
   Model and effort are preferences: joined into one segmented control and
   toned down, so three identical pills stop competing for attention. */
.chip.chip-primary {{
  font-size: 12px;
  font-weight: 800;
  padding: 6px 15px;
  box-shadow: {lift_soft};
}}
.engine-group {{
  background: {sunken};
  border: 1px solid {edge};
  border-radius: 999px;
  padding: 2px;
}}
.chip.chip-quiet {{
  background: transparent;
  border: 1px solid transparent;
  color: {muted};
  font-size: 10px;
  font-weight: 600;
  padding: 3px 10px;
  box-shadow: none;
}}
.chip.chip-quiet:hover {{ background: {chip_hi}; color: {fg}; }}

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

.pending-keys {{
  font-family: "JetBrainsMono Nerd Font", monospace;
  font-size: 10px;
  font-weight: 700;
  color: {accent};
  background: {accent_lo};
  border: 1px solid {accent_edge};
  border-radius: {r_sm};
  padding: 1px 6px;
  margin: 0 9px 6px 0;
}}
.notice-icon {{ font-size: 14px; color: {warn}; }}
.notice-fix, .notice-retry {{
  background: linear-gradient(180deg, {warn_hi}, {warn_lo});
  border: 1px solid {warn_edge};
  border-radius: {r_md};
  padding: 4px 12px;
  font-size: 11px;
  font-weight: 700;
  color: {warn};
  min-height: 0;
}}
.notice-fix:hover, .notice-retry:hover {{
  background: linear-gradient(180deg, {warn}, {warn_deep});
  color: {bg};
}}
.mono  {{ font-family: "JetBrainsMono Nerd Font", monospace; font-size: 12px; color: {fg}; }}
.small {{ font-size: 11px; color: {muted}; }}
.error {{ font-size: 12px; color: {bad}; }}

.secret {{
  background: {sunken_deep};
  border: 1px solid {bad_edge};
  border-radius: {r_md};
  padding: 9px 11px;
  font-family: "JetBrainsMono Nerd Font", monospace;
  font-size: 13px;
  color: {fg};
}}

/* ---- history -------------------------------------------------------- */
.hit {{ border-radius: {r_md}; padding: 8px 12px; font-size: 12px; color: {muted}; }}
.hit.on {{ background: linear-gradient(180deg, {accent_hi}, {accent_lo});
           color: {fg}; border: 1px solid {accent_edge}; }}
.hit-meta {{ font-size: 10px; color: {faint};
             font-family: "JetBrainsMonoNL Nerd Font", monospace; }}

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


def theme_source():
    """The file wallust rewrites; watching it is what makes re-theming live."""
    return rofi_theme.COLORS_SCSS


def _alpha(hex_colour: str, pct: int) -> str:
    value = hex_colour.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{pct / 100:.2f})"


def css() -> str:
    colours = rofi_theme._read_colors()
    bg, fg, accent = colours["bg"], colours["fg"], colours["accent"]
    warn, bad = "#E4B363", "#D2696A"
    deep = rofi_theme._mix(accent, bg, 0.35)
    # A cooler second accent, for things that are informational rather than
    # active: links, mostly. One accent doing every job - mode chip, selection,
    # links, pending keys, command names - meant none of them read as special.
    link = rofi_theme._mix(accent, "#5AC8FA", 0.72)
    return TEMPLATE.format(
        bg=bg, fg=fg, accent=accent, warn=warn, bad=bad,
        accent_deep=deep,
        link=link,
        link_edge=_alpha(link, 55),

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
        # The window itself: translucent so the compositor's blur shows through.
        glass_hi=_alpha(rofi_theme._mix(bg, fg, 0.10), 82),
        glass=_alpha(bg, 78),
        glass_lo=_alpha(rofi_theme._mix(bg, "#000000", 0.25), 82),
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
