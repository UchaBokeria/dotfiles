//! The installer's inputs: what to install, where things go, what to run.
//!
//! All three files are data, not code, and they live beside this crate in
//! `installer/data/`. That split is the point: the rice changes constantly, and
//! a change to it should be a line in a TOML file rather than a change to the
//! program that applies it. `installer/data/README.md` says how they are kept
//! honest.

use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use serde::Deserialize;

#[derive(Debug, Deserialize, Default)]
pub struct Meta {
    #[serde(default)]
    pub generated: String,
    #[serde(default)]
    pub host: String,
    #[serde(default)]
    pub aur_helper: String,
    #[serde(default)]
    pub hyprland: String,
}

// ---------------------------------------------------------------- packages --

#[derive(Debug, Deserialize, Clone)]
pub struct Package {
    pub name: String,
    /// `repo` for the official repositories, `aur` for everything else.
    #[serde(default = "default_source")]
    pub source: String,
    #[serde(default)]
    pub why: String,
}

fn default_source() -> String {
    "repo".to_string()
}

impl Package {
    pub fn is_aur(&self) -> bool {
        self.source.eq_ignore_ascii_case("aur")
    }
}

#[derive(Debug, Deserialize, Clone)]
pub struct Group {
    pub name: String,
    /// A required group cannot be unticked: without it the rice does not run.
    #[serde(default)]
    pub required: bool,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub packages: Vec<Package>,
}

#[derive(Debug, Deserialize, Default)]
pub struct Packages {
    #[serde(default)]
    pub meta: Meta,
    #[serde(default, rename = "group")]
    pub groups: Vec<Group>,
}

// ------------------------------------------------------------------- links --

#[derive(Debug, Deserialize, Clone)]
pub struct Link {
    /// Path inside the repo.
    pub repo: String,
    /// Where it belongs, `~` allowed.
    pub target: String,
    /// `symlink`, `copy`, or `generated` - generated files are written by the
    /// theme pipeline and must never be linked, or the generator would be
    /// writing into the repo through its own symlink.
    #[serde(default = "default_kind")]
    pub kind: String,
    /// Personal or secret-bearing: skipped unless the machine is this machine.
    #[serde(default)]
    pub personal: bool,
    #[serde(default)]
    pub note: String,
}

fn default_kind() -> String {
    "symlink".to_string()
}

#[derive(Debug, Deserialize, Clone)]
pub struct Setting {
    /// `gsettings` or `xfconf`. Anything that needs ordering, a root prompt or
    /// a check is a step, not a setting - a key/value pair cannot carry those.
    pub tool: String,
    pub key: String,
    #[serde(default)]
    pub value: String,
    #[serde(default)]
    pub note: String,
    #[serde(default)]
    pub personal: bool,
    /// Exits 0 when the value is already what it should be.
    #[serde(default)]
    pub check: String,
}

#[derive(Debug, Deserialize, Default)]
pub struct Links {
    #[serde(default)]
    pub meta: Meta,
    #[serde(default, rename = "link")]
    pub links: Vec<Link>,
    #[serde(default, rename = "setting")]
    pub settings: Vec<Setting>,
}

// ------------------------------------------------------------------- steps --

#[derive(Debug, Deserialize, Clone)]
pub struct Step {
    pub id: String,
    pub title: String,
    #[serde(default)]
    pub run: Vec<String>,
    /// Exits 0 when the step has already been done. Every step has one: the
    /// installer is run again on a machine that is half set up more often than
    /// on a fresh one.
    #[serde(default)]
    pub check: String,
    #[serde(default)]
    pub root: bool,
    /// Needs a running Hyprland session, so it belongs to the second phase
    /// after the first login.
    #[serde(default)]
    pub needs_session: bool,
    #[serde(default)]
    pub optional: bool,
    /// Runs before the package groups rather than after them. `pacman -Sy`
    /// followed by `-S` is how a partial upgrade happens, so the system update
    /// cannot be just another step at the end of the list.
    #[serde(default)]
    pub first: bool,
    #[serde(default)]
    pub after: Vec<String>,
    #[serde(default)]
    pub note: String,
    /// Which optional package group this step belongs to, if any.
    #[serde(default)]
    pub group: String,
}

#[derive(Debug, Deserialize, Default)]
pub struct Steps {
    #[serde(default)]
    pub meta: Meta,
    #[serde(default, rename = "step")]
    pub steps: Vec<Step>,
}

/// One thing the installer has to ask, because the machine cannot answer it.
///
/// Everything that CAN be detected is detected - `detect` runs a command and
/// its output becomes the default, so the question is usually a confirmation
/// rather than an interrogation. The answer is exported to every step as
/// `env`, which is how a keyboard with no Super key ends up in machine.lua.
#[derive(Debug, Deserialize, Clone, Default)]
pub struct Question {
    pub id: String,
    pub title: String,
    #[serde(default)]
    pub note: String,
    /// Environment variable the answer is exported as.
    pub env: String,
    /// Shell command whose stdout is the default answer. Optional.
    #[serde(default)]
    pub detect: String,
    /// Fallback default when `detect` is absent or produces nothing.
    #[serde(default)]
    pub default: String,
    /// Fixed choices. Empty means the detected/default value is simply
    /// confirmed - there is nothing to pick between.
    #[serde(default, rename = "option")]
    pub options: Vec<Choice>,
}

#[derive(Debug, Deserialize, Clone, Default)]
pub struct Choice {
    pub value: String,
    #[serde(default)]
    pub label: String,
    #[serde(default)]
    pub note: String,
}

#[derive(Debug, Deserialize, Default)]
pub struct Questions {
    #[serde(default)]
    pub meta: Meta,
    #[serde(default, rename = "question")]
    pub questions: Vec<Question>,
}

// ------------------------------------------------------------------ loading --

pub struct Catalogue {
    pub packages: Packages,
    pub links: Links,
    pub steps: Steps,
    pub questions: Questions,
    pub root: PathBuf,
}

impl Catalogue {
    pub fn load(root: &Path) -> Result<Self> {
        let dir = root.join("installer/data");
        Ok(Self {
            packages: read(&dir.join("packages.toml"))?,
            links: read(&dir.join("links.toml"))?,
            steps: read(&dir.join("steps.toml"))?,
            questions: read(&dir.join("questions.toml"))?,
            root: root.to_path_buf(),
        })
    }
}

fn read<T: serde::de::DeserializeOwned + Default>(path: &Path) -> Result<T> {
    if !path.exists() {
        // A missing catalogue is a bug in the repo, not in the machine, so say
        // which file and carry on with nothing rather than dying in a TUI the
        // user cannot read.
        eprintln!("blackwall-install: missing {}", path.display());
        return Ok(T::default());
    }
    let text = std::fs::read_to_string(path)
        .with_context(|| format!("reading {}", path.display()))?;
    toml::from_str(&text).with_context(|| format!("parsing {}", path.display()))
}

/// Expand a leading `~` against the real home directory.
///
/// A bare `~` counts. It used not to, and the consequence was not cosmetic:
/// the backup path is built by stripping `expand("~")` off the target, so an
/// unexpanded `"~"` made that strip fail, and joining the untouched ABSOLUTE
/// path onto the backup root discarded the root entirely. The file was then
/// renamed onto itself and overwritten a moment later - a backup that quietly
/// destroyed the thing it was meant to save.
pub fn expand(path: &str) -> PathBuf {
    let home = || std::env::var("HOME").ok().map(PathBuf::from);
    if path == "~" {
        if let Some(home) = home() {
            return home;
        }
    }
    if let Some(rest) = path.strip_prefix("~/") {
        if let Some(home) = home() {
            return home.join(rest);
        }
    }
    PathBuf::from(path)
}
