//! Everything the installer asks the machine before it proposes anything.
//!
//! The rule this module exists to keep: nothing is assumed. Every package is
//! checked against pacman, every link against the filesystem, every step
//! against its own `check` command. The plan the user approves is built from
//! the answers, so a second run on a half-installed machine proposes only what
//! is actually left.

use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use crate::data::{self, Link, Package};

#[derive(Debug, Clone)]
pub struct System {
    pub is_arch: bool,
    pub distro: String,
    pub aur_helper: Option<String>,
    pub has_network: bool,
    /// A Wayland session is running, so session-only steps can be done now.
    pub in_session: bool,
    pub hyprland: Option<String>,
    pub home: PathBuf,
    pub user: String,
    pub shell: String,
    pub sudo_ready: bool,
}

pub fn probe() -> System {
    let home = std::env::var("HOME").map(PathBuf::from).unwrap_or_default();
    let user = std::env::var("USER").unwrap_or_else(|_| "user".into());
    System {
        is_arch: Path::new("/etc/arch-release").exists(),
        distro: os_release_name(),
        aur_helper: ["yay", "paru", "pikaur", "trizen"]
            .iter()
            .find(|h| which(h))
            .map(|h| h.to_string()),
        has_network: run_ok("ping -c1 -W2 archlinux.org >/dev/null 2>&1"),
        in_session: std::env::var("WAYLAND_DISPLAY").is_ok(),
        hyprland: capture("hyprctl version -j")
            .and_then(|out| {
                out.split("\"tag\":").nth(1).map(|rest| {
                    rest.trim_start()
                        .trim_start_matches('"')
                        .split('"')
                        .next()
                        .unwrap_or("")
                        .to_string()
                })
            })
            .filter(|v| !v.is_empty()),
        shell: capture(&format!("getent passwd {user} | cut -d: -f7"))
            .unwrap_or_default()
            .trim()
            .to_string(),
        sudo_ready: run_ok("sudo -n true >/dev/null 2>&1"),
        home,
        user,
    }
}

fn os_release_name() -> String {
    std::fs::read_to_string("/etc/os-release")
        .ok()
        .and_then(|text| {
            text.lines()
                .find(|l| l.starts_with("PRETTY_NAME="))
                .map(|l| l.trim_start_matches("PRETTY_NAME=").trim_matches('"').to_string())
        })
        .unwrap_or_else(|| "unknown".into())
}

pub fn which(binary: &str) -> bool {
    run_ok(&format!("command -v {binary} >/dev/null 2>&1"))
}

/// True when pacman already has the package. `-Qq` covers AUR packages too:
/// once installed they are ordinary local packages.
pub fn pkg_installed(name: &str) -> bool {
    run_ok(&format!("pacman -Qq {} >/dev/null 2>&1", shell_quote(name)))
}

pub fn missing(packages: &[Package]) -> Vec<Package> {
    packages
        .iter()
        .filter(|p| !pkg_installed(&p.name))
        .cloned()
        .collect()
}

#[derive(Debug, Clone, PartialEq)]
pub enum LinkState {
    /// Already points where it should.
    Correct,
    /// Nothing there; free to create.
    Missing,
    /// Something else is there. The path is what would be backed up.
    Conflict(PathBuf),
    /// The source is not in the repo - a stale entry in the catalogue.
    NoSource,
}

pub fn link_state(link: &Link, repo: &Path) -> LinkState {
    let source = repo.join(&link.repo);
    let target = data::expand(&link.target);
    if !source.exists() {
        return LinkState::NoSource;
    }
    match std::fs::symlink_metadata(&target) {
        Err(_) => LinkState::Missing,
        Ok(meta) => {
            if meta.file_type().is_symlink() {
                match std::fs::read_link(&target) {
                    Ok(dest) if dest == source => LinkState::Correct,
                    // A link into the repo by another route (relative, or via
                    // a symlinked home) is still correct.
                    Ok(dest) => {
                        let resolved = if dest.is_absolute() {
                            dest
                        } else {
                            target.parent().unwrap_or(Path::new("/")).join(dest)
                        };
                        match (resolved.canonicalize(), source.canonicalize()) {
                            (Ok(a), Ok(b)) if a == b => LinkState::Correct,
                            _ => LinkState::Conflict(target),
                        }
                    }
                    Err(_) => LinkState::Conflict(target),
                }
            } else if link.kind == "copy" {
                // A copy is a plain file, so it can never be "our symlink".
                // Compare the bytes instead: same content means the machine is
                // already in the state the catalogue asks for. Without this
                // every copied file counted as a conflict on every run, and
                // each run backed it up and wrote it again.
                match (std::fs::read(&source), std::fs::read(&target)) {
                    (Ok(a), Ok(b)) if a == b => LinkState::Correct,
                    _ => LinkState::Conflict(target),
                }
            } else {
                LinkState::Conflict(target)
            }
        }
    }
}

/// Run a step's `check`. An empty check means "cannot tell", which is treated
/// as not done - doing idempotent work twice is cheaper than skipping work
/// that was never done.
pub fn check_passes(check: &str, cwd: &Path) -> bool {
    if check.trim().is_empty() {
        return false;
    }
    Command::new("sh")
        .arg("-c")
        .arg(check)
        .current_dir(cwd)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

pub fn run_ok(cmd: &str) -> bool {
    Command::new("sh")
        .arg("-c")
        .arg(cmd)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

pub fn capture(cmd: &str) -> Option<String> {
    let out = Command::new("sh").arg("-c").arg(cmd).output().ok()?;
    if !out.status.success() {
        return None;
    }
    Some(String::from_utf8_lossy(&out.stdout).to_string())
}

/// Is this key/value pair already what it should be?
///
/// Every `[[setting]]` in the catalogue was listed as "to do" on a machine that
/// already had it: none of them carries a `check` of its own, and
/// `check_passes("")` is false by definition. Asking the tool what the value is
/// now means the plan tells the truth about 51 settings instead of promising
/// work it does not need to do.
pub fn setting_satisfied(setting: &data::Setting, cwd: &Path) -> bool {
    if !setting.check.trim().is_empty() {
        return check_passes(&setting.check, cwd);
    }
    let current = match setting.tool.as_str() {
        "gsettings" => {
            let mut parts = setting.key.split_whitespace();
            let (Some(schema), Some(key)) = (parts.next(), parts.next()) else {
                return false;
            };
            capture(&format!(
                "gsettings get {} {}",
                shell_quote(schema),
                shell_quote(key)
            ))
        }
        "xfconf" => {
            let Some((channel, property)) = setting.key.split_once(char::is_whitespace) else {
                return false;
            };
            capture(&format!(
                "xfconf-query -c {} -p {}",
                shell_quote(channel.trim()),
                shell_quote(property.trim())
            ))
        }
        _ => None,
    };
    match current {
        Some(got) => unquote(got.trim()) == unquote(setting.value.trim()),
        // No value to read - the schema may not exist, or the tool is missing.
        // Either way it is not satisfied, and running it will say why.
        None => false,
    }
}

/// `gsettings get` prints a string with its quotes still on; the catalogue
/// stores the bare value, because that is what `gsettings set` wants.
fn unquote(value: &str) -> &str {
    value
        .strip_prefix('\'')
        .and_then(|rest| rest.strip_suffix('\''))
        .unwrap_or(value)
}

/// Catalogue entries whose source is not in this clone.
///
/// The failure this catches: a file that works here because it exists on this
/// machine, but was never committed - so a fresh clone installs a rice with a
/// hole in it. Cheap to check and the answer is always interesting.
pub fn missing_sources(cat: &crate::data::Catalogue, repo: &Path) -> Vec<String> {
    cat.links
        .links
        .iter()
        .filter(|l| !l.personal && l.kind != "generated")
        .filter(|l| !repo.join(&l.repo).exists())
        .map(|l| l.repo.clone())
        .collect()
}

/// Single-quote for `sh -c`. Package and path names come from a file in the
/// repo rather than from the network, but they still reach a shell.
pub fn shell_quote(s: &str) -> String {
    format!("'{}'", s.replace('\'', r"'\''"))
}
