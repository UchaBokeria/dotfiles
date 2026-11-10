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

Card anatomy, floating and panel alike: a normal card is the ordinary raised
surface with a hairline ring. Only critical is marked - a soft bad-tinted glow
bleeding in from the left edge under a faint bad ring, no hard stripe. Action
buttons are pills, like every other button in the rice, full width of the card's
content. The close button is a 28px disc inset in the top-right corner,
revealed by swaync only while the pointer is over the card, bad-tinted on its
own hover. Corners are half the minimum card height - the bar's capsule
proportions, held fixed - and every gap in the stack comes from one spacing
scale (see `swaync()`).

Critical used to be a 3px solid bar down the left edge. It read as a red
bookmark stuck to the side of the card rather than something the card itself
was saying, and it was the one place in the rice with a hard-edged coloured
stripe. The glow is the same signal made out of the paint the rest of the glass
already uses - a gradient, not a border.
"""

from __future__ import annotations

from ..tokens import Tokens
from . import header

#: Cards share one minimum height, floating and panel alike, so a one-line
#: notification is not a sliver and the close button always has the same room
#: above the text. There is deliberately no maximum: `max-height` on the card
#: measures the wrong thing - the label inside does not ellipsize to it, and
#: the row collapses past it into illegible overlap instead of clamping. The
#: body's line budget belongs to swaync, which already caps popups at five
#: lines; a config value for that (`notification-window-height`) only measures
#: the whole popup stack, not one card, so a twelve-line body is drawn in full
#: and that is fixed upstream, not here.
CARD_MIN = 72

#: The close disc's diameter. It sets the clearance the text keeps from the
#: right edge, so it is a constant here rather than a literal in two rules.
CLOSE = 28

#: Where the close disc sits, measured from the card's right edge.
CLOSE_INSET = 12

#: The height of every small pill control in the stack - the actions under a
#: card, the inline-reply entry and button, the panel's "clear all". One height
#: so a button row and a reply row read as one family. The vertical padding is
#: a spacing token and `min-height` is whatever remains, so the total holds
#: whatever the label's own line height turns out to be.
CONTROL_H = 28

#: swaync puts 2px between consecutive rows on its own, in the popup stack and
#: the panel list alike (measured: with every padding and margin zeroed, two
#: cards are still 2px apart). The row padding makes up the rest of the gap.
ROW_SPACING = 2


def px(value: str) -> int:
    """`"18px"` -> 18. The spacing tokens are strings; the arithmetic that
    keeps the card's insets on one scale needs numbers."""
    return int(value.removesuffix("px"))


def swaync(tokens: Tokens) -> str:
    t = tokens
    # One spacing scale for the whole notification stack, all from the tokens:
    #   PAD_Y  12  card's top and bottom padding, and the buttons' bottom
    #   PAD_X  18  card's left and right padding (the text and the buttons)
    #   GAP     8  text to buttons, button to button, card to card
    # The card-to-card gap is swaync's own 2px plus a little padding on each
    # neighbour's row, so a stack is GAP apart.
    pad_y, pad_x, gap = px(t.s_lg), px(t.s_xl), px(t.s_md)
    half = gap // 2
    row_pad = (gap - ROW_SPACING) // 2
    content_min = CARD_MIN - 2 * pad_y
    # A pill control: vertical padding s_sm, horizontal s_lg (both on the
    # scale), and the content box takes what is left of CONTROL_H. GTK adds
    # padding outside `min-height`; the border is set to none (the ring is a
    # box-shadow) so it adds nothing either.
    ctl_pad_y, ctl_pad_x = px(t.s_sm), px(t.s_lg)
    ctl_min = CONTROL_H - 2 * ctl_pad_y
    close_top = (CARD_MIN - CLOSE) // 2
    # Corner radius: a waybar capsule is a stadium, radius = half its height.
    # A card's height varies, so it takes half of its *minimum* height instead
    # and keeps that corner however tall it grows.
    radius = CARD_MIN // 2
    # The critical glow: a bad-tinted gradient entering from the left edge and
    # gone by 46%. The popup's is a touch stronger, because it sits on a
    # wallpaper instead of the panel's own glass.
    def glow(a0: int, a1: int) -> str:
        return (f"linear-gradient(to right,\n"
                f"      {t.bad.alpha(a0).css} 0%,\n"
                f"      {t.bad.alpha(a1).css} 18%,\n"
                f"      {t.bad.alpha(0).css} 46%)")
    glow_panel, glow_popup = glow(14, 8), glow(16, 9)
    # The pill's hover fill darkens or lightens toward a sheen colour. On_accent
    # is picked against the plain accent, so the sheen must move AWAY from the
    # text colour (toward the lighter pole when the text is dark, the darker
    # when it is light): mixing toward bg regardless dropped dark-on-accent
    # text to ~3:1 at the hover gradient's end and the pressed fill.
    lighter, darker = sorted((t.bg, t.fg), key=lambda c: c.luminance)[::-1]
    sheen = lighter if t.on_accent.luminance < t.accent.luminance else darker
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
  /* The title's text starts where a card's text does. */
  padding: 0 0 0 {pad_x}px;
}}

.control-center .widget-title button {{
  background: linear-gradient(to bottom,
    {t.raised_hi.css} 0%,
    {t.raised_lo.css} 100%);
  color: {t.muted.css};
  border: none;
  border-radius: {t.r_pill};
  box-shadow: inset 0 0 0 1px {t.edge.css};
  /* The same control as an action pill, in the muted ink of a secondary
     control. */
  min-height: {ctl_min}px;
  padding: {ctl_pad_y}px {ctl_pad_x}px;
  margin: 0;
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
/* swaync gives every widget 8px of margin and 8px of padding. Inside the
   panel's own padding that left the list 17px further in than the title and
   the DND row, so the cards looked inset against everything above them. The
   widgets are flush; the panel's padding is the only gutter, and the gap
   between one widget and the next is the card gap. */
.widget {{
  margin: 0 0 {gap}px;
  padding: 0;
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
  margin: 0;
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

/* The row's own box wraps each card. swaync's default gives it 6px top and
   bottom with 12px on the sides. Here it is the card-to-card gap: what swaync's
   own row spacing leaves of it, split above and below each card, and nothing
   at the sides in the panel (the cards are flush with the widgets above them).
   The popups add the same at the sides, where the window's edge is the only
   other margin. */
.notification-row .notification-background {{
  background: transparent;
  padding: {row_pad}px 0;
}}

/* A card is a pane, not a cell: it gets the same three-stop glass gradient as
   every other panel in the rice, dimmed to sit inside a panel that is already
   glass. A flat fill made each row read as a hole cut in the panel; the
   gradient gives it the same lit-from-top-left body the popups have, so a row
   lifted out of the centre and the popup it becomes look like one thing.

   A panel card sits on `.control-center`, whose own gradient is behind it, so
   the stops here are tinted more conservatively than a popup's - see the
   floating rules below, where the same gradient sits on the wallpaper. */
.notification {{
  background: linear-gradient(to bottom,
    {t.raised_hi.css} 0%,
    {t.raised_lo.css} 100%);
  /* Waybar's capsules are pills (r_pill). A card cannot be a true pill - it
     grows with its body and a tall one would balloon into an ellipse - so it
     takes the pill's proportions at the card's own minimum height: a radius
     of half CARD_MIN. A one- or two-line card is then a stadium exactly like
     a bar capsule, and a taller one keeps the same corner instead of
     scaling it. Panel and popup share it. */
  border-radius: {radius}px;
  box-shadow: inset 0 0 0 1px {t.edge.css}, inset 0 1px 0 {t.rim_top.css};
  padding: 0;
  margin: 0;
}}
.control-center .notification:hover {{
  background: linear-gradient(to bottom,
    {t.raised_hi.css} 0%,
    {t.hover.css} 100%);
}}
/* A hover rule is more specific than `.notification.critical`, so without this
   one a critical card lost its glow the moment the pointer touched it. */
.control-center .notification.critical:hover {{
  background:
    {glow_panel},
    linear-gradient(to bottom,
      {t.raised_hi.css} 0%,
      {t.hover.css} 100%);
}}
/* The close button is not inside `.notification`: swaync overlays it on
   `.notification-background`, the card's parent (checked against the
   GtkBuilder UI compiled into swaync 0.12.6). A selector that goes through
   `.notification` never matches it. `:hover` is set on every ancestor of the
   hovered widget, so the overlay is hovered whenever the card or the button
   is. */
.control-center .notification-background:hover .close-button {{
  background: {t.raised_hi.css};
  color: {t.fg.css};
}}
.control-center .notification-background .close-button:hover {{
  background: {t.bad_hi.css};
  color: {t.bad.css};
}}

/* keyboard-shortcuts is on in config.json, so swaync moves a focus ring
   through the list. Unstyled, GTK draws its own - a yellow dashed rectangle
   that belongs to no palette here. This is the same ring the rest of the rice
   uses for a selected row. */
.notification-row:focus .notification,
.notification:focus,
.notification:focus-within {{
  box-shadow: inset 0 0 0 1px {t.accent_edge.css};
  outline: none;
}}
.notification-row:focus,
.notification-row:focus-visible,
.control-center-list row,
.control-center-list row:focus,
.control-center-list row:focus-visible {{
  outline: none;
  outline-color: transparent;
  box-shadow: none;
}}

/* The whole card is one click target: clicking a notification runs its
   `default` action, from the popup and from the list alike. The face itself
   stays unpainted - the card underneath carries the hover - so there is no
   double wash, just the behaviour. */
.notification-default-action {{
  background: transparent;
  border: none;
  box-shadow: none;
  padding: 0;
  margin: 0;
  border-radius: {radius}px;
}}
.notification-default-action:hover {{ background: transparent; }}
.notification-default-action:not(:only-child) {{
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
}}

.notification-content {{
  background: transparent;
  /* Equal left and right: the text sits {pad_x}px in from both edges, top and
     bottom {pad_y}px. The min-height is what makes a card without buttons
     {CARD_MIN}px tall, and swaync's text box is vertically centred (valign
     center, vexpand) inside whatever the content box is, so a one-line card
     centres its line rather than hanging it from the top. */
  padding: {pad_y}px {pad_x}px;
  min-height: {content_min}px;
}}
/* With buttons the card is content, gap, buttons. The text no longer needs a
   centring band - the buttons are what the spare height is for - and it has
   no bottom padding of its own, because the gap to the buttons is the
   buttons' top padding. */
.notification-default-action:not(:only-child) .notification-content {{
  min-height: 0;
  padding-bottom: 0;
}}
/* The close disc occupies the last {CLOSE_INSET + CLOSE}px of the card. The
   text keeps {CLOSE}px out of the way beyond the shared padding, which is the
   one place left and right padding differ. */
.text-box {{
  margin-right: {CLOSE}px;
}}

/* swaync's own `.image` margin is 4px all round, which put the icon 4px in
   from the text's left edge and made an icon card 4px taller than every other
   card (44px icon + 8px margin + 24px padding = 76). The icon is flush with
   the text column, and the only space it keeps is the gap to the text. */
.notification-content .image {{
  margin: 0 {gap}px 0 0;
}}

.summary {{
  color: {t.fg.css};
  font-size: {t.t_sm};
  font-weight: 700;
}}
.body {{
  color: {t.muted.css};
  font-size: {t.t_sm};
}}
/* The time sits at the end of the summary line. swaync's own CSS clears it
   30px from the edge for the overlay close button; here `.text-box` carries
   that clearance for the whole text block, so the time's own margin goes. */
.time {{
  color: {t.faint.css};
  font-size: {t.t_xs};
  /* A long summary ellipsizes right up against the time; the gap keeps them
     apart. */
  margin: 0 0 0 {gap}px;
}}

/* Urgency, as a glow.

   It used to be a bar down the left edge - first `inset 3px 0 0`, which a
   rounded corner sliced into a wedge tapering away at both ends, then a real
   3px border to fix the taper. The border was technically correct and still
   looked wrong: a hard-edged red stripe pinned to the side of a card reads as
   a bookmark, not as something the card is saying, and it was the only
   hard-edged coloured stripe in the rice.

   This is the same signal built from paint the rest of the glass already
   uses. A short gradient enters from the left edge and is gone by the middle
   of the card, so the tint is strongest where the eye lands and never turns
   into a wash; a faint bad ring carries the rest. Both are background and
   box-shadow, so the card's box is identical in every urgency - it cannot
   reflow when a notification becomes critical.

   Only critical is marked. Normal and low share the ordinary surface: a wall
   of coloured rows makes none of them urgent, and the ones that matter are
   rare. There is deliberately no app-icon and no stripe on a normal card. */
.notification.critical {{
  background:
    {glow_panel},
    linear-gradient(to bottom,
      {t.raised_hi.css} 0%,
      {t.raised_lo.css} 100%);
  box-shadow: inset 0 0 0 1px {t.bad_edge.css},
    inset 0 1px 0 {t.rim_top.css};
}}
.notification.low,
.notification.normal {{ box-shadow: inset 0 0 0 1px {t.edge.css}; }}

/* ---- action buttons ----------------------------------------------------- */
/* The reason for the swap. mako renders actions as click targets on the whole
   notification, so a notification with three actions had one usable one.
   Pills, like every button in the rice.

   swaync lays these out in a horizontal FlowBox with `homogeneous: true`, so
   one action does not stretch to the full width - but the default height and
   padding made even a single "Later" a wide flat slab. The geometry here keeps
   them compact and pills, and gives them the same lit-from-above gradient the
   rest of the rice's buttons use instead of one flat fill.

   `.notification-alt-actions` is the FlowBox; only its inner buttons carry
   paint, so the row of them contributes no surface of its own. */
.notification-alt-actions {{
  background: transparent;
  /* Top is the gap to the text, bottom is the card's padding, and the sides
     are the card's padding less the half-gap each action already carries -
     so the outer buttons sit exactly {pad_x}px from the edge, in line with
     the text. */
  padding: {gap}px {pad_x - half}px {pad_y}px;
}}

/* Half a gap on each side of every action: {gap}px between two buttons. The
   row padding above is short by the same half-gap at the ends, so the outer
   buttons are still {pad_x}px from the edge. */
.notification-action {{
  background: transparent;
  margin: 0;
  padding: 0 {half}px;
}}

.notification-action > button,
.inline-reply-button {{
  background: linear-gradient(to bottom,
    {t.raised_hi.css} 0%,
    {t.raised_lo.css} 100%);
  color: {t.accent.css};
  border: none;
  border-radius: {t.r_pill};
  box-shadow: inset 0 0 0 1px {t.accent_edge.css};
  /* {CONTROL_H}px tall: padding {ctl_pad_y}px top and bottom (s_sm) and a
     {ctl_min}px content box, enough to hit, short enough that a row of three
     still leaves the body the majority of the card. Margin is zero: the
     row's own padding is the only spacing, so one button is the full width of
     the content area and two or three split it evenly (swaync's FlowBox is
     `homogeneous`). */
  min-height: {ctl_min}px;
  padding: {ctl_pad_y}px {ctl_pad_x}px;
  margin: 0;
  font-size: {t.t_xs};
  font-weight: 600;
}}
.notification-action > button:hover,
.inline-reply-button:hover {{
  background: linear-gradient(to bottom,
    {t.accent.css} 0%,
    {t.accent.mix(sheen, 0.16).css} 100%);
  color: {t.on_accent.css};
  box-shadow: inset 0 0 0 1px {t.accent_edge.css};
}}
/* Pressed: the sheen goes and the fill is the plain accent, flat, so a click
   registers as the button being pushed in rather than as nothing happening.
   Flat accent is what on_accent was chosen against, so it is always legible. */
.notification-action > button:active,
.inline-reply-button:active {{
  background: {t.accent.css};
  color: {t.on_accent.css};
}}
/* The reply button has nothing to send until something is typed. */
.inline-reply-button:disabled {{
  background: {t.raised_lo.css};
  color: {t.faint.css};
  box-shadow: inset 0 0 0 1px {t.edge.css};
}}

/* ---- inline reply, progress and body image -------------------------------- */
/* swaync's own stylesheet puts a 4px top margin on each of these, on top of the
   8px the content box already puts between its children - 12px, which is on no
   scale here. The margins go; the box's 8px is the gap. */
.notification-content progressbar,
.notification-content .body-image,
.notification-content .inline-reply {{
  margin-top: 0;
}}
.notification-content progressbar trough {{
  background: {t.sunken.css};
  border-radius: {t.r_pill};
}}
.notification-content progressbar progress {{
  background: {t.accent.css};
  border-radius: {t.r_pill};
}}
/* The image a body can carry (`<img src>`): the control radius, so it does not
   sit as a hard rectangle inside a card made of stadiums. */
.notification-content .body-image {{
  border-radius: {t.r_md};
}}
/* The reply row: a pill entry and the pill button beside it, one control
   height, the button a gap away. */
.inline-reply-entry {{
  background: {t.sunken.css};
  color: {t.fg.css};
  caret-color: {t.fg.css};
  border: none;
  border-radius: {t.r_pill};
  box-shadow: inset 0 0 0 1px {t.edge.css};
  outline: none;
  min-height: {CONTROL_H}px;
  padding: 0 {ctl_pad_x}px;
  font-size: {t.t_xs};
}}
.inline-reply-entry:focus-within {{
  box-shadow: inset 0 0 0 1px {t.accent_edge.css};
}}
.inline-reply-entry text,
.inline-reply-entry placeholder {{
  color: {t.faint.css};
}}
.inline-reply-entry text {{ color: {t.fg.css}; }}
.inline-reply-button {{ margin-left: {gap}px; }}

/* ---- the close button --------------------------------------------------- */
/* An overlay in the card's top-right corner, inside a GtkRevealer that swaync
   opens only while the pointer is over the card - so a screenshot with the
   cursor elsewhere shows no button at all, and no CSS can make it visible at
   rest (2026-10-28: an agent read that as "never paints"; hovering proves it
   does).

   {CLOSE}px across, inset {CLOSE_INSET}px from the card's right edge, and pinned to the
   TOP rather than the card's centre: the overlay is as tall as the card, so a
   centre alignment parks the button in the middle of a tall card, nowhere near
   the text it belongs to. The top margin centres it in the first {CARD_MIN}px
   of the card - the whole of a card without buttons, and the text band of one
   with - so it lines up with the middle of a short card and with the summary
   line of a taller one.

   The overlay is the row's box, which has {row_pad}px of padding around the
   card, so every offset here carries that too. The text keeps clear of the
   disc with `.text-box`'s right margin. */
.close-button {{
  background: {t.hover.css};
  color: {t.muted.css};
  border-radius: {t.r_pill};
  margin: {close_top + row_pad}px {CLOSE_INSET}px 0 0;
  padding: 0;
  min-width: {CLOSE}px;
  min-height: {CLOSE}px;
}}
.close-button:hover {{
  background: {t.bad_hi.css};
  color: {t.bad.css};
}}

/* ---- floating notifications --------------------------------------------- */

.floating-notifications {{
  background: transparent;
}}
.floating-notifications .notification-row {{
  padding: 0;
  margin: 0;
}}
/* Popups are {gap}px apart, the same as panel rows: the same row padding on
   every side, no margin on the card itself. The row's box is also what clips
   a card's drop shadow, and {row_pad}px has no room for the 14px `lift`, so a
   popup takes the soft lift (1px, 3px blur) - it is still glass on a
   wallpaper, only the shadow is tighter. */
.floating-notifications .notification-background {{
  padding: {row_pad}px;
}}
/* The stack's distance from the screen edge is the rice's gutter, the same as
   the control centre's, less the row padding the card already has. */
.floating-notifications > scrolledwindow {{
  margin-right: {px(t.gutter) - row_pad}px;
}}
.floating-notifications .notification {{
  background: {t.gradient()};
  box-shadow: {t.ring(t.lift_soft)};
  margin: 0;
}}
.floating-notifications .close-button {{
  margin-right: {CLOSE_INSET + row_pad}px;
}}
/* The popup carries the same glow as a panel row, over its own glass fill
   rather than the flat raised one. */
.floating-notifications .notification.critical {{
  background:
    {glow_popup},
    {t.gradient()};
  box-shadow: inset 0 0 0 1px {t.bad_edge.css}, {t.lift_soft};
}}

/* ---- scrollbars --------------------------------------------------------- */
/* The control centre is two nested GtkScrolledWindows with automatic policy:
   the outer one is the `.control-center` node itself (it wraps the whole
   widget stack: title, DND, list) and the inner one holds just the
   notification list. The list is the one that really scrolls. The outer one
   ends up a few pixels shorter than its content as well, so it grew a bar of
   its own, drawn over the inner one at the same right edge - two scrollbars.
   The outer is hidden (it has nothing worth scrolling to), the inner is the
   only bar: a thin pill, faint at rest and brighter under the pointer, on a
   transparent trough. */
scrollbar {{
  background: transparent;
  box-shadow: none;
  margin: {pad_y}px 0;
  padding: 0;
}}
/* GTK's overlay scrollbar widens to a ~20px slab under the pointer - a slider
   with an 8px transparent border on every side, which in a column of rounded
   cards reads as a grey rectangle laid over their right edge. The borders go
   and the width is pinned to 4px, at rest and hovered alike. */
scrollbar.vertical,
scrollbar.vertical trough,
scrollbar.vertical slider {{
  min-width: 4px;
  margin: 0;
  padding: 0;
}}
scrollbar range,
scrollbar trough,
scrollbar slider {{
  border: none;
  border-width: 0;
  outline: none;
}}
scrollbar trough {{ background: transparent; box-shadow: none; }}
scrollbar slider {{
  min-height: 36px;
  background: {t.faint.css};
  border-radius: {t.r_pill};
  box-shadow: none;
}}
scrollbar slider:hover {{
  background: {t.muted.css};
}}
scrollbar slider:active {{
  background: {t.accent.css};
}}
/* After the rules above, which match both bars: the outer one is a direct
   child of `.control-center`, and goes. */
.control-center > scrollbar {{
  opacity: 0;
  min-width: 0;
  min-height: 0;
  margin: 0;
  padding: 0;
}}
.control-center > scrollbar slider {{
  min-width: 0;
  min-height: 0;
}}

/* ---- widgets ------------------------------------------------------------ */

/* The DND row is a capsule like the cards under it: the card's gradient, its
   ring and its radius, and the same 12/18 padding. The panel's next widget is
   the notification list, whose first row already carries {row_pad}px of its own
   padding, so the margin here is the card gap less that - the gap from this
   row to the first card is {gap}px, the same as between two cards. */
.widget-dnd {{
  background: linear-gradient(to bottom,
    {t.raised_hi.css} 0%,
    {t.raised_lo.css} 100%);
  border-radius: {radius}px;
  box-shadow: inset 0 0 0 1px {t.edge.css}, inset 0 1px 0 {t.rim_top.css};
  padding: {pad_y}px {pad_x}px;
  margin-bottom: {gap - row_pad}px;
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
  padding: {pad_y}px {pad_x}px;
  margin-bottom: {gap}px;
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
