//! The screens.
//!
//! Everything is drawn from `App`; no screen keeps state of its own. The frame
//! counter drives the animation, so a redraw during a long pacman run costs
//! one pass over a handful of lines.

use ratatui::layout::{Alignment, Constraint, Direction, Layout, Rect};
use ratatui::style::Style;
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, BorderType, Borders, List, ListItem, Paragraph, Wrap};
use ratatui::Frame;

use crate::banner;
use crate::plan::{Item, State};
use crate::theme::{self, glyph};
use crate::{App, Screen};

pub fn draw(f: &mut Frame, app: &App) {
    let area = f.area();
    f.render_widget(
        Block::default().style(Style::default().bg(theme::BG)),
        area,
    );

    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(banner::HEIGHT + 3),
            Constraint::Min(6),
            Constraint::Length(2),
        ])
        .split(area);

    masthead(f, app, chunks[0]);
    match app.screen {
        Screen::Welcome => welcome(f, app, chunks[1]),
        Screen::Groups => groups(f, app, chunks[1]),
        Screen::Questions => questions(f, app, chunks[1]),
        Screen::Wallpaper => wallpaper(f, app, chunks[1]),
        Screen::Plan => plan(f, app, chunks[1]),
        Screen::Running => running(f, app, chunks[1]),
        Screen::Done => done(f, app, chunks[1]),
    }
    footer(f, app, chunks[2]);
}

fn masthead(f: &mut Frame, app: &App, area: Rect) {
    let mut lines = banner::render(app.frame);
    lines.push(banner::tagline(app.frame));
    lines.push(banner::rule(area.width.saturating_sub(2)));
    f.render_widget(
        Paragraph::new(lines).alignment(Alignment::Left),
        inset(area),
    );
}

fn welcome(f: &mut Frame, app: &App, area: Rect) {
    let s = &app.system;
    let ok = |b: bool| {
        if b {
            Span::styled(format!("{} ", glyph::CHECK), theme::good())
        } else {
            Span::styled(format!("{} ", glyph::CROSS), theme::bad())
        }
    };
    let mut lines = vec![
        Line::from(Span::styled("the machine", theme::title())),
        Line::from(""),
        Line::from(vec![ok(s.is_arch), Span::styled(s.distro.clone(), theme::body())]),
        Line::from(vec![
            ok(s.has_network),
            Span::styled(
                if s.has_network { "network reachable" } else { "no network - packages cannot be fetched" },
                theme::body(),
            ),
        ]),
        Line::from(vec![
            ok(s.aur_helper.is_some()),
            Span::styled(
                match &s.aur_helper {
                    Some(h) => format!("AUR helper: {h}"),
                    None => "no AUR helper - the AUR packages will be deferred".into(),
                },
                theme::body(),
            ),
        ]),
        Line::from(vec![
            ok(s.in_session),
            Span::styled(
                match &s.hyprland {
                    Some(v) => format!("graphical session (Hyprland {v})"),
                    None => "no graphical session - session steps come after the first login".into(),
                },
                theme::body(),
            ),
        ]),
        // Not a failure: sudo simply has not been asked yet. A red cross here
        // read as "something is wrong" on every single run.
        Line::from(vec![
            if s.sudo_ready {
                Span::styled(format!("{} ", glyph::CHECK), theme::good())
            } else {
                Span::styled(format!("{} ", glyph::DOT), theme::warn())
            },
            Span::styled(
                if s.sudo_ready { "sudo ready" } else { "sudo will ask for your password once" },
                theme::body(),
            ),
        ]),
        Line::from(""),
        Line::from(Span::styled(
            format!(
                "{} package groups · {} files · {} setup steps in the catalogue",
                app.catalogue.packages.groups.len(),
                app.catalogue.links.links.len(),
                app.catalogue.steps.steps.len()
            ),
            theme::muted(),
        )),
    ];
    if !s.is_arch {
        lines.push(Line::from(""));
        lines.push(Line::from(Span::styled(
            "This rice is Arch-shaped: it installs with pacman and builds a Hyprland plugin.",
            theme::warn(),
        )));
    }
    // 34 files in the rice - waybar module exec lines, hypr binds, the systemd
    // units, the scripts themselves - name ~/.config/.dotfiles/blackwall
    // outright. Linking the configs from anywhere else produces a rice whose
    // every button points at a path that does not exist, and it would look
    // like a successful install.
    let expected = crate::data::expand("~/.config/.dotfiles/blackwall");
    if app.repo != expected {
        lines.push(Line::from(""));
        lines.push(Line::from(Span::styled(
            "this clone is not where the rice expects to live".to_string(),
            theme::bad(),
        )));
        lines.push(Line::from(Span::styled(
            format!("  here:     {}", app.repo.display()),
            theme::warn(),
        )));
        lines.push(Line::from(Span::styled(
            format!("  expected: {}", expected.display()),
            theme::warn(),
        )));
        lines.push(Line::from(Span::styled(
            "  waybar modules, hypr binds and the systemd units name that path outright",
            theme::faint(),
        )));
    }
    if !app.missing_sources.is_empty() {
        lines.push(Line::from(""));
        lines.push(Line::from(Span::styled(
            format!(
                "{} file(s) the catalogue expects are not in this clone:",
                app.missing_sources.len()
            ),
            theme::bad(),
        )));
        for path in app.missing_sources.iter().take(6) {
            lines.push(Line::from(Span::styled(
                format!("  {} {}", glyph::CROSS, path),
                theme::warn(),
            )));
        }
        lines.push(Line::from(Span::styled(
            "  they exist on the machine this came from but were never committed",
            theme::faint(),
        )));
    }
    f.render_widget(
        Paragraph::new(lines).wrap(Wrap { trim: true }).block(pane("preflight")),
        inset(area),
    );
}

fn groups(f: &mut Frame, app: &App, area: Rect) {
    let items: Vec<ListItem> = app
        .catalogue
        .packages
        .groups
        .iter()
        .enumerate()
        .map(|(i, g)| {
            let on = g.required || app.selected.contains(&g.name);
            let mark = if g.required {
                Span::styled(format!("{} ", glyph::BOX_FULL), theme::faint())
            } else if on {
                Span::styled(format!("{} ", glyph::BOX_FULL), Style::default().fg(theme::ACCENT))
            } else {
                Span::styled(format!("{} ", glyph::BOX_EMPTY), theme::faint())
            };
            let name = if i == app.cursor {
                Span::styled(format!(" {:<12}", g.name), theme::selected())
            } else {
                Span::styled(format!(" {:<12}", g.name), theme::body())
            };
            let count = Span::styled(format!(" {:>3} pkgs  ", g.packages.len()), theme::faint());
            let note = Span::styled(
                if g.required {
                    format!("required — {}", g.description)
                } else {
                    g.description.clone()
                },
                theme::muted(),
            );
            ListItem::new(Line::from(vec![mark, name, count, note]))
        })
        .collect();
    f.render_widget(List::new(items).block(pane("what to install")), inset(area));
}

/// The few things the machine cannot work out for itself.
///
/// Each row is one question with its current answer; left/right move through
/// the choices. Anything with a `detect` opens on what was found, so the usual
/// interaction here is to read four lines and press enter.
fn questions(f: &mut Frame, app: &App, area: Rect) {
    let mut lines = vec![
        Line::from(Span::styled(
            "detected where possible - change anything that is wrong for this machine",
            theme::muted(),
        )),
        Line::from(""),
    ];
    for (i, q) in app.catalogue.questions.questions.iter().enumerate() {
        let at = app.answer_at.get(i).copied().unwrap_or(0);
        let chosen = q.options.get(at);
        let selected_row = i == app.cursor;
        lines.push(Line::from(vec![
            Span::styled(
                if selected_row { format!("{} ", glyph::ARROW) } else { "  ".to_string() },
                Style::default().fg(theme::ACCENT),
            ),
            Span::styled(
                q.title.clone(),
                if selected_row { theme::selected() } else { theme::body() },
            ),
        ]));
        // A question with no options is typed into. A secret shows its length
        // and nothing else - the whole point is that it is not readable over
        // anyone's shoulder or in a screenshot of this screen.
        let typed = app.typed.get(&i);
        let label = if q.options.is_empty() {
            match (q.secret, typed) {
                (true, Some(v)) if !v.is_empty() => "•".repeat(v.chars().count().min(40)),
                (true, _) => "(not set - type to enter, or leave empty to skip)".into(),
                (false, Some(v)) if !v.is_empty() => v.clone(),
                (false, _) => q.default.clone(),
            }
        } else {
            chosen
                .map(|o| if o.label.is_empty() { o.value.clone() } else { o.label.clone() })
                .unwrap_or_else(|| q.default.clone())
        };
        let arrows = if q.options.len() > 1 {
            "  ‹ › "
        } else if q.options.is_empty() {
            "  ❯   "
        } else {
            "      "
        };
        lines.push(Line::from(vec![
            Span::styled(arrows.to_string(), theme::faint()),
            Span::styled(
                label,
                if selected_row {
                    Style::default().fg(theme::ACCENT)
                } else {
                    theme::body()
                },
            ),
            Span::styled(
                chosen
                    .map(|o| if o.note.is_empty() { String::new() } else { format!("   {}", o.note) })
                    .unwrap_or_default(),
                theme::faint(),
            ),
        ]));
        if selected_row && !q.note.is_empty() {
            for line in q.note.trim().lines().take(4) {
                lines.push(Line::from(Span::styled(
                    format!("      {line}"),
                    theme::muted(),
                )));
            }
        }
        lines.push(Line::from(""));
    }
    f.render_widget(
        Paragraph::new(lines).wrap(Wrap { trim: false }).block(pane("a few questions")),
        inset(area),
    );
}

fn wallpaper(f: &mut Frame, app: &App, area: Rect) {
    let inner = inset(area);
    let rows = inner.height.saturating_sub(4) as usize;
    let start = app.cursor.saturating_sub(rows.saturating_sub(1));
    let mut lines = vec![
        Line::from(Span::styled(
            "the whole palette - bar, panels, terminal, GTK, Qt - is derived from this one image",
            theme::muted(),
        )),
        Line::from(""),
    ];
    for (i, name) in app.wallpapers.iter().enumerate().skip(start).take(rows) {
        let chosen = i == app.wallpaper;
        let mark = if chosen { glyph::BOX_FULL } else { glyph::BOX_EMPTY };
        let label = format!(" {name}");
        lines.push(Line::from(vec![
            Span::styled(
                format!("{mark} "),
                if chosen { Style::default().fg(theme::ACCENT) } else { theme::faint() },
            ),
            if i == app.cursor {
                Span::styled(label, theme::selected())
            } else {
                Span::styled(label, theme::body())
            },
        ]));
    }
    if app.wallpapers.is_empty() {
        lines.push(Line::from(Span::styled(
            "no images in wallpapers/ - the theme step will fall back to its default",
            theme::warn(),
        )));
    }
    f.render_widget(Paragraph::new(lines).block(pane("first wallpaper")), inner);
}

fn plan(f: &mut Frame, app: &App, area: Rect) {
    let inner = inset(area);
    let rows = inner.height.saturating_sub(3) as usize;
    let start = app.cursor.saturating_sub(rows.saturating_sub(1));
    let items: Vec<ListItem> = app
        .items
        .iter()
        .enumerate()
        .skip(start)
        .take(rows)
        .map(|(i, item)| ListItem::new(item_line(item, i == app.cursor)))
        .collect();
    f.render_widget(
        List::new(items).block(pane(&format!("the plan — {}", crate::plan::summary(&app.items)))),
        inner,
    );
}

fn item_line(item: &Item, cursor: bool) -> Line<'static> {
    let (mark, style) = match &item.state {
        State::Todo => (glyph::ARROW, theme::body()),
        State::Satisfied => (glyph::CHECK, theme::faint()),
        State::Deferred(_) => (glyph::DOT, theme::muted()),
        State::Conflict(_) => ("!", theme::warn()),
        State::Running => (glyph::ARROW, Style::default().fg(theme::ACCENT)),
        State::Done => (glyph::CHECK, theme::good()),
        State::Failed(_) => (glyph::CROSS, theme::bad()),
        State::Skipped => ("-", theme::faint()),
    };
    let title = if cursor {
        Span::styled(format!(" {:<44}", trunc(&item.title, 44)), theme::selected())
    } else {
        Span::styled(format!(" {:<44}", trunc(&item.title, 44)), style)
    };
    let detail = match &item.state {
        State::Deferred(why) | State::Conflict(why) | State::Failed(why) => {
            Span::styled(trunc(why, 60), theme::warn())
        }
        _ => Span::styled(trunc(&item.detail, 60), theme::faint()),
    };
    Line::from(vec![
        Span::styled(format!("{mark} "), style),
        title,
        Span::raw(" "),
        detail,
    ])
}

fn running(f: &mut Frame, app: &App, area: Rect) {
    let inner = inset(area);
    let split = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Length(4), Constraint::Min(4)])
        .split(inner);

    let done = app.finished;
    let total = app.todo_total.max(1);
    let width = split[0].width.saturating_sub(4) as usize;
    let filled = width * done / total;
    let bar: Vec<Span> = (0..width)
        .map(|i| {
            if i < filled {
                Span::styled(glyph::BAR_FULL, Style::default().fg(theme::gradient(i, width)))
            } else {
                Span::styled("─", theme::faint())
            }
        })
        .collect();

    let spin = glyph::SPINNER[(app.frame / 2) % glyph::SPINNER.len()];
    let head = Line::from(vec![
        Span::styled(format!("{spin} "), Style::default().fg(theme::ACCENT)),
        Span::styled(trunc(&app.current, 70), theme::body()),
    ]);
    let count = Line::from(Span::styled(
        format!("  {done}/{total} · {}", app.elapsed()),
        theme::faint(),
    ));
    f.render_widget(
        Paragraph::new(vec![head, Line::from(bar), count]),
        split[0],
    );

    let rows = split[1].height.saturating_sub(2) as usize;
    let log: Vec<ListItem> = app
        .log
        .iter()
        .rev()
        .take(rows)
        .rev()
        .map(|line| {
            let style = if line.starts_with("$ ") {
                Style::default().fg(theme::LINK)
            } else if line.contains("error") || line.contains("failed") {
                theme::bad()
            } else {
                theme::faint()
            };
            ListItem::new(Line::from(Span::styled(trunc(line, split[1].width as usize - 4), style)))
        })
        .collect();
    f.render_widget(List::new(log).block(pane("output")), split[1]);
}

fn done(f: &mut Frame, app: &App, area: Rect) {
    let failed: Vec<&Item> = app
        .items
        .iter()
        .filter(|i| matches!(i.state, State::Failed(_)))
        .collect();
    let deferred: Vec<&Item> = app
        .items
        .iter()
        .filter(|i| matches!(i.state, State::Deferred(_)))
        .collect();

    let mut lines = vec![
        Line::from(Span::styled(
            if failed.is_empty() { "done" } else { "done, with failures" },
            if failed.is_empty() { theme::good() } else { theme::warn() },
        )),
        Line::from(""),
        Line::from(Span::styled(crate::plan::summary(&app.items), theme::muted())),
        Line::from(""),
    ];
    if let Some(backup) = &app.backup {
        lines.push(Line::from(Span::styled(
            format!("this run is recorded in {}", backup.display()),
            theme::body(),
        )));
        lines.push(Line::from(Span::styled(
            "  ./install --restore   puts back what was moved aside, removes what was added",
            theme::faint(),
        )));
        lines.push(Line::from(""));
    }
    for item in failed.iter().take(6) {
        if let State::Failed(why) = &item.state {
            lines.push(Line::from(vec![
                Span::styled(format!("{} ", glyph::CROSS), theme::bad()),
                Span::styled(trunc(&item.title, 40), theme::body()),
                Span::styled(format!("  {}", trunc(why, 40)), theme::faint()),
            ]));
        }
    }
    if !deferred.is_empty() {
        lines.push(Line::from(""));
        lines.push(Line::from(Span::styled(
            "after you log into Hyprland, run ./install again for:",
            theme::body(),
        )));
        for item in deferred.iter().take(8) {
            lines.push(Line::from(Span::styled(
                format!("  {} {}", glyph::DOT, trunc(&item.title, 60)),
                theme::muted(),
            )));
        }
    }
    lines.push(Line::from(""));
    lines.push(Line::from(Span::styled(
        "docs/cheatsheet.md is the map: every keybind, script and trap.",
        theme::faint(),
    )));
    f.render_widget(
        Paragraph::new(lines).wrap(Wrap { trim: true }).block(pane("blackwall")),
        inset(area),
    );
}

fn footer(f: &mut Frame, app: &App, area: Rect) {
    let conflicts = app
        .items
        .iter()
        .filter(|i| matches!(i.state, State::Conflict(_)))
        .count();
    let keys = match app.screen {
        Screen::Welcome => "enter continue · q quit".to_string(),
        Screen::Groups => "space toggle · ↑↓ move · enter continue · q quit".to_string(),
        Screen::Questions => {
            "↑↓ question · ←→ answer · type to fill a blank · enter continue · esc back"
                .to_string()
        }
        Screen::Wallpaper => "↑↓ choose · enter continue · esc back · q quit".to_string(),
        Screen::Plan if conflicts > 0 => format!(
            "enter install · space skip item · d dry run · esc back · {conflicts} in the way will be backed up"
        ),
        Screen::Plan => "enter install · space skip item · d dry run · ↑↓ move · esc back · q quit".to_string(),
        Screen::Running => "q abort after the current step".to_string(),
        Screen::Done => "q quit".to_string(),
    };
    let mut spans = vec![Span::styled(format!("  {keys}"), theme::faint())];
    if app.dry_run {
        spans.push(Span::styled("   [dry run: nothing will change]", theme::warn()));
    }
    f.render_widget(
        Paragraph::new(vec![banner::rule(area.width.saturating_sub(2)), Line::from(spans)]),
        inset(area),
    );
}

// ---- small helpers ------------------------------------------------------

fn pane(title: &str) -> Block<'static> {
    Block::default()
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(Style::default().fg(theme::gradient_dim(0, 1, 0.5)))
        .title(Span::styled(format!(" {title} "), theme::title()))
}

fn inset(area: Rect) -> Rect {
    Rect {
        x: area.x + 2,
        y: area.y,
        width: area.width.saturating_sub(4),
        height: area.height,
    }
}

fn trunc(s: &str, max: usize) -> String {
    if s.chars().count() <= max {
        s.to_string()
    } else {
        let kept: String = s.chars().take(max.saturating_sub(1)).collect();
        format!("{kept}…")
    }
}
