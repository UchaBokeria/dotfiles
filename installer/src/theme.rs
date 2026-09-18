//! The installer's palette.
//!
//! These are the rice's own tokens, hardcoded rather than read from
//! `theme/blackwall_theme/tokens.py`: the installer runs before the rice
//! exists, on a machine with no wallpaper to derive a palette from, so there
//! is nothing to read yet. The values below are the fallback accent family the
//! token generator itself falls back to, so the installer looks like the thing
//! it is about to install.

use ratatui::style::{Color, Modifier, Style};

pub const BG: Color = Color::Rgb(0x14, 0x15, 0x1c);
pub const FG: Color = Color::Rgb(0xe8, 0xe8, 0xf0);
pub const MUTED: Color = Color::Rgb(0x9a, 0x9a, 0xa8);
pub const FAINT: Color = Color::Rgb(0x5e, 0x5e, 0x6b);
pub const ACCENT: Color = Color::Rgb(0xec, 0x71, 0xf5);
pub const LINK: Color = Color::Rgb(0x83, 0xb0, 0xf9);
pub const WARN: Color = Color::Rgb(0xe4, 0xb3, 0x63);
pub const BAD: Color = Color::Rgb(0xd2, 0x69, 0x6a);
pub const GOOD: Color = Color::Rgb(0x7f, 0xb8, 0x8a);

pub fn title() -> Style {
    Style::default().fg(ACCENT).add_modifier(Modifier::BOLD)
}

pub fn body() -> Style {
    Style::default().fg(FG)
}

pub fn muted() -> Style {
    Style::default().fg(MUTED)
}

pub fn faint() -> Style {
    Style::default().fg(FAINT)
}

pub fn good() -> Style {
    Style::default().fg(GOOD)
}

pub fn warn() -> Style {
    Style::default().fg(WARN)
}

pub fn bad() -> Style {
    Style::default().fg(BAD)
}

pub fn selected() -> Style {
    Style::default()
        .fg(Color::Rgb(0x14, 0x15, 0x1c))
        .bg(ACCENT)
        .add_modifier(Modifier::BOLD)
}

/// Colour for position `i` of `len`, magenta running into blue.
///
/// One gradient used for the banner, the rules and the progress bar, so the
/// screen reads as one object rather than as three widgets that happen to be
/// stacked.
pub fn gradient(i: usize, len: usize) -> Color {
    let t = if len <= 1 {
        0.0
    } else {
        (i as f32) / ((len - 1) as f32)
    };
    let (r1, g1, b1) = (0xec as f32, 0x71 as f32, 0xf5 as f32);
    let (r2, g2, b2) = (0x5a as f32, 0xc8 as f32, 0xfa as f32);
    Color::Rgb(
        (r1 + (r2 - r1) * t) as u8,
        (g1 + (g2 - g1) * t) as u8,
        (b1 + (b2 - b1) * t) as u8,
    )
}

/// The same gradient, dimmed. Used for the parts of a frame that should be
/// present but not read: rules, inactive borders, the scanline's tail.
pub fn gradient_dim(i: usize, len: usize, factor: f32) -> Color {
    match gradient(i, len) {
        Color::Rgb(r, g, b) => Color::Rgb(
            (r as f32 * factor) as u8,
            (g as f32 * factor) as u8,
            (b as f32 * factor) as u8,
        ),
        other => other,
    }
}

/// Marks used throughout, kept in one place so the screens agree.
pub mod glyph {
    pub const CHECK: &str = "✓";
    pub const CROSS: &str = "✗";
    pub const DOT: &str = "•";
    pub const ARROW: &str = "›";
    pub const BOX_EMPTY: &str = "□";
    pub const BOX_FULL: &str = "▣";
    pub const BAR_FULL: &str = "█";
    /// Braille spinner: eight frames that read as motion rather than as text.
    pub const SPINNER: [&str; 8] = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧"];
}
