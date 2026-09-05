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
  background: {t.glass.css};
  border-radius: {t.r_window};
  box-shadow: {t.ring};
  margin: 12px;
  padding: 14px;
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

.notification-row {{
  background: transparent;
  padding: 3px 0;
}}

.notification {{
  background: {t.raised_lo.css};
  border-radius: {t.r_md};
  box-shadow: inset 0 0 0 1px {t.edge.css};
  padding: 0;
  margin: 0;
}}
.notification:hover {{ background: {t.hover.css}; }}

.notification-content {{
  background: transparent;
  padding: 10px 12px;
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
  border-radius: {t.r_sm};
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
  background: {t.glass.css};
  box-shadow: {t.ring};
  border-radius: {t.r_lg};
  margin: 8px;
}}
.floating-notifications .notification.critical {{
  background: {t.bad_hi.css};
  box-shadow: inset 0 0 0 1px {t.bad_edge.css}, {t.ring};
}}

/* ---- widgets ------------------------------------------------------------ */

.widget-dnd {{
  background: {t.raised_lo.css};
  border-radius: {t.r_md};
  box-shadow: inset 0 0 0 1px {t.edge.css};
  padding: 10px 12px;
  margin-bottom: 8px;
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

  background: {t.raised_lo.css};
  border-radius: {t.r_md};
  box-shadow: inset 0 0 0 1px {t.edge.css};
  padding: 10px;
  margin-bottom: 8px;
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
