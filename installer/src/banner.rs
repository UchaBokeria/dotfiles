//! The masthead: BLACKWALL in block letters, with a scanline running down it
//! and an occasional glitch.
//!
//! The animation is a pure function of a frame counter. Nothing here owns a
//! timer or a thread, so the installer can redraw whenever it likes - during a
//! package install the frame counter simply advances more slowly, and the
//! banner degrades into a still image rather than into a stutter.

use ratatui::style::Style;
use ratatui::text::{Line, Span};

use crate::theme;

/// A 5-row block font, wide enough to read and narrow enough to fit an 80
/// column terminal with room to spare.
fn glyph(c: char) -> [&'static str; 5] {
    match c {
        'B' => ["███ ", "█  █", "███ ", "█  █", "███ "],
        'L' => ["█   ", "█   ", "█   ", "█   ", "████"],
        'A' => [" ██ ", "█  █", "████", "█  █", "█  █"],
        'C' => [" ███", "█   ", "█   ", "█   ", " ███"],
        'K' => ["█  █", "█ █ ", "██  ", "█ █ ", "█  █"],
        'W' => ["█   █", "█ █ █", "█ █ █", "██ ██", "█   █"],
        _ => ["    ", "    ", "    ", "    ", "    "],
    }
}

const WORD: &str = "BLACKWALL";

/// Height of the rendered banner, in terminal rows.
pub const HEIGHT: u16 = 5;

/// Render the banner for `frame`.
///
/// Three things move:
///   * the gradient runs magenta to cyan across the whole word,
///   * a scanline brightens one row and dims the row behind it,
///   * every so often a row tears sideways for a frame or two.
pub fn render(frame: usize) -> Vec<Line<'static>> {
    let rows: Vec<String> = (0..5)
        .map(|row| {
            WORD.chars()
                .map(|c| glyph(c)[row].to_string())
                .collect::<Vec<_>>()
                .join(" ")
        })
        .collect();

    // The scanline sweeps down the five rows and then pauses below the word,
    // so the eye gets a rest between passes instead of a strobe.
    let cycle = 14;
    let scan = (frame / 2) % cycle;

    // A tear every few cycles, one row, a couple of frames long. Rare enough
    // to read as a glitch rather than as a fault.
    let tearing = frame % 97 < 2;
    let tear_row = (frame / 97) % 5;

    rows.into_iter()
        .enumerate()
        .map(|(row, text)| {
            let text = if tearing && row == tear_row {
                let shift = 3usize.min(text.len());
                let (head, tail) = text.split_at(text.len() - shift);
                format!("{tail}{head}")
            } else {
                text
            };

            let lit = row == scan;
            let trailing = scan > 0 && row + 1 == scan;
            let len = text.chars().count();
            let spans: Vec<Span> = text
                .chars()
                .enumerate()
                .map(|(i, ch)| {
                    let colour = if lit {
                        theme::gradient(i, len)
                    } else if trailing {
                        theme::gradient_dim(i, len, 0.75)
                    } else {
                        theme::gradient_dim(i, len, 0.45)
                    };
                    Span::styled(ch.to_string(), Style::default().fg(colour))
                })
                .collect();
            Line::from(spans)
        })
        .collect()
}

/// The line under the banner: a tagline that types itself out once.
pub fn tagline(frame: usize) -> Line<'static> {
    const TEXT: &str = "a hyprland rice, installed whole";
    let shown = (frame / 2).min(TEXT.chars().count());
    let typed: String = TEXT.chars().take(shown).collect();
    let cursor = if shown < TEXT.chars().count() && frame % 8 < 4 {
        "▌"
    } else {
        " "
    };
    Line::from(vec![
        Span::styled("  ", theme::faint()),
        Span::styled(typed, theme::muted()),
        Span::styled(cursor.to_string(), Style::default().fg(theme::ACCENT)),
    ])
}

/// A horizontal rule in the same gradient, for separating regions.
pub fn rule(width: u16) -> Line<'static> {
    let width = width as usize;
    let spans: Vec<Span> = (0..width)
        .map(|i| {
            Span::styled(
                "─".to_string(),
                Style::default().fg(theme::gradient_dim(i, width, 0.55)),
            )
        })
        .collect();
    Line::from(spans)
}
