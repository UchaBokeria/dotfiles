"""SwayNotificationCenter's stylesheet.

swaync is a GTK4 app with its own CSS, so unlike mako it can carry the whole
glass vocabulary: gradients, rims, radii and motion. That is most of why it is
worth the swap - mako's config language has one background colour per urgency
and no notion of a panel at all, so a notification centre had to be built
beside it rather than in it.

The selectors here are swaync's own; they are not GTK generics. `.control-center`
is the panel, `.notification-row` a row inside it, `.notification-action` one of
the buttons an application attaches to a notification - the thing mako could
never draw.
"""

from __future__ import annotations

from ..tokens import Tokens
from . import header


def swaync(tokens: Tokens) -> str:
    t = tokens
    return header("/*", "*/", tokens=tokens) + f"""
* {{
  font-family: {t.font_ui};
  font-size: {t.t_md};
}}

/* ---- the panel ---------------------------------------------------------- */
/* Transparent window, glass on the pane inside it. The compositor blurs the
   layer (see hypr/configs/windowrules.conf, namespace swaync-control-center),
   so the panel needs alpha rather than a solid fill or the blur has nothing to
   show through it. */

.control-center {{
  background: {t.gradient()};
  border-radius: {t.r_lg};
  box-shadow: {t.ring()};
  /* 12 here plus swaync's own 8 in config.json is the 20px gutter. */
  margin: {t.s_lg};
  padding: {t.s_xl};
}}

.control-center .widget-title {{
  color: {t.muted.css};
  font-size: {t.t_xs};
  font-weight: 700;
  padding: 2px 4px 8px;
}}

.control-center .widget-title button {{
  background: {t.raised_lo.css};
  color: {t.muted.css};
  border-radius: {t.r_pill};
  box-shadow: inset 0 0 0 1px {t.edge.css};
  padding: 3px 12px;
  font-size: {t.t_xs};
}}
.control-center .widget-title button:hover {{
  background: {t.hover.css};
  color: {t.fg.css};
}}

/* ---- a notification ----------------------------------------------------- */

/* Every container between the panel and a card is transparent. Measured
   across a row, there was a 14px band of a lighter surface on each side of the
   card - swaync's own `.widget` box, 8px margin plus 8px padding - so each
   notification sat in a second container around content that already has one.
   The card is the surface; nothing else needs to be. */
.control-center-list,
.notification-group,
.widget {{
  background: transparent;
}}
.control-center-list-placeholder {{
  color: {t.faint.css};
  font-size: {t.t_xs};
}}

/* One card per row, with the list's own rhythm between them. swaync groups
   notifications by app by default and draws a collapsed group as cards stacked
   behind each other; with two apps repeating themselves the stacks ran into the
   row below and the list read as overlapping rectangles. Grouping is off in
   config.json, and these rules make sure that even if it comes back on, a group
   is a plain container with no geometry of its own. */
.notification-row {{
  background: transparent;
  padding: 0;
  margin: 0 0 {t.s_xs} 0;
}}
.notification-group {{
  margin: 0;
  padding: 0;
}}
.notification-group-headers,
.notification-group-icon {{
  color: {t.muted.css};
  font-size: {t.t_xs};
  padding: 0 4px 4px;
}}
.notification-group-collapse-button,
.notification-group-close-all-button {{
  background: transparent;
  color: {t.faint.css};
  box-shadow: none;
  padding: 0 6px;
}}

.notification {{
  background: {t.raised_lo.css};
  border-radius: {t.r_md};
  box-shadow: inset 0 0 0 1px {t.edge.css};
  padding: 0;
  margin: 0;
}}
.notification:hover {{ background: {t.hover.css}; }}

/* keyboard-shortcuts is on in config.json, so swaync moves a focus ring
   through the list. Unstyled, GTK draws its own - a yellow dashed rectangle
   that belongs to no palette here. This is the same ring the rest of the rice
   uses for a selected row. */
.notification-row:focus .notification,
.notification:focus,
.notification:focus-within {{
  background: {t.hover.css};
  box-shadow: inset 0 0 0 1px {t.accent_edge.css};
  outline: none;
}}
.notification-row:focus,
.notification-row:focus-visible {{
  outline: none;
}}

.notification-content {{
  background: transparent;
  padding: {t.pad_row};
}}

.summary {{
  color: {t.fg.css};
  font-size: {t.t_sm};
  font-weight: 600;
}}
.body {{
  color: {t.muted.css};
  font-size: {t.t_xs};
}}
.time {{
  color: {t.faint.css};
  font-size: {t.t_xs};
}}

/* Urgency, without the stripe.
   
   It used to be `inset 3px 0 0` down the left edge. An inset box-shadow is
   clipped by the border-radius, so on an 18px corner the stripe was sliced
   into a wedge that tapered away at both ends - a coloured smear following the
   curve rather than a bar. It looked like a rendering fault, because it very
   nearly is one.
   
   Only critical is marked now, and by tinting the whole card and its ring.
   Normal and low share the ordinary surface: a wall of coloured rows makes
   none of them urgent, and the ones that matter are rare. */
.notification.critical {{
  background: {t.bad_hi.css};
  box-shadow: inset 0 0 0 1px {t.bad_edge.css};
}}
.notification.low,
.notification.normal {{ box-shadow: inset 0 0 0 1px {t.edge.css}; }}

/* ---- action buttons ----------------------------------------------------- */
/* The reason for the swap. mako renders actions as click targets on the whole
   notification, so a notification with three actions had one usable one. */

.notification-action {{
  background: {t.raised_hi.css};
  color: {t.fg.css};
  border-radius: {t.r_md};
  box-shadow: inset 0 0 0 1px {t.edge.css};
  margin: 0 4px 8px 4px;
  padding: 5px 10px;
  font-size: {t.t_xs};
}}
.notification-action:hover {{
  background: {t.accent.css};
  color: {t.on_accent.css};
}}

.close-button {{
  background: transparent;
  color: {t.faint.css};
  border-radius: {t.r_pill};
  margin: 6px;
  padding: 0;
  min-width: 22px;
  min-height: 22px;
}}
.close-button:hover {{
  background: {t.bad_hi.css};
  color: {t.bad.css};
}}

/* ---- floating notifications --------------------------------------------- */

.floating-notifications .notification {{
  background: {t.gradient()};
  box-shadow: {t.ring(t.lift)};
  border-radius: {t.r_lg};
  margin: {t.s_md};
}}
.floating-notifications .notification.critical {{
  background: {t.bad_hi.css};
  box-shadow: inset 0 0 0 1px {t.bad_edge.css}, {t.ring(t.lift)};
}}

/* ---- widgets ------------------------------------------------------------ */

.widget-dnd {{
  background: {t.raised_lo.css};
  border-radius: {t.r_md};
  box-shadow: inset 0 0 0 1px {t.edge.css};
  padding: {t.s_lg};
  margin-bottom: {t.s_lg};
  color: {t.fg.css};
  font-size: {t.t_sm};
}}
.widget-dnd > switch {{
  background: {t.sunken.css};
  border-radius: {t.r_pill};
  box-shadow: inset 0 0 0 1px {t.edge.css};
}}
.widget-dnd > switch:checked {{ background: {t.accent.css}; }}
.widget-dnd > switch slider {{
  background: {t.fg.css};
  border-radius: {t.r_pill};
}}

.widget-mpris {{
  background: {t.raised_lo.css};
  border-radius: {t.r_md};
  box-shadow: inset 0 0 0 1px {t.edge.css};
  padding: {t.s_lg};
  margin-bottom: {t.s_lg};
}}
.widget-mpris-subtitle {{ color: {t.faint.css}; font-size: {t.t_xs}; }}

.widget-label {{ color: {t.muted.css}; font-size: {t.t_xs}; }}

.widget-buttons-grid {{
  background: transparent;
  padding: 0;
}}
.widget-buttons-grid > flowbox > flowboxchild > button {{
  background: {t.raised_lo.css};
  color: {t.fg.css};
  border-radius: {t.r_md};
  box-shadow: inset 0 0 0 1px {t.edge.css};
  margin: 3px;
  padding: 10px;
}}
.widget-buttons-grid > flowbox > flowboxchild > button:hover {{
  background: {t.hover.css};
}}
"""
