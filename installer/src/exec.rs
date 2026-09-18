//! Doing the work, on a worker thread, reporting every line back to the UI.
//!
//! Two rules shape this module. Nothing destroys anything: a file in the way is
//! moved into a timestamped backup directory, never deleted, and `--restore`
//! puts it back. And nothing runs that was not on the approved plan - the UI
//! hands over a list, and this runs exactly that list in order.

use std::io::{BufRead, BufReader};
use std::os::unix::fs::symlink;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::mpsc::Sender;

use crate::data::{self, Setting};
use crate::plan::{Action, Item};
use crate::probe;

pub enum Event {
    /// A line of output from whatever is running.
    Line(String),
    /// Item `index` has started.
    Start(usize),
    /// Item `index` finished; `Err` carries the reason.
    Finish(usize, Result<(), String>),
    /// Everything is done. Carries the backup directory, if one was made.
    AllDone(Option<PathBuf>),
    /// Root is needed and the cached credential has expired.
    NeedSudo,
}

/// Written inside the backup directory: one line per file this run created
/// where nothing existed before. Without it `--restore` could only put back
/// what it moved aside, leaving every new symlink behind.
const MANIFEST: &str = ".blackwall-created";

pub struct Runner {
    pub repo: PathBuf,
    pub dry_run: bool,
    pub backup: PathBuf,
    /// What the questions screen was told, as environment variables. Every
    /// step sees them, which is how "this keyboard has no Super key" reaches
    /// the shell line that writes machine.lua.
    pub answers: Vec<(String, String)>,
}

impl Runner {
    pub fn new(repo: PathBuf, dry_run: bool) -> Self {
        let stamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);
        let backup = data::expand("~/.local/state/blackwall/backups")
            .join(format!("{stamp}"));
        Self { repo, dry_run, backup, answers: Vec::new() }
    }

    pub fn with_answers(mut self, answers: Vec<(String, String)>) -> Self {
        self.answers = answers;
        self
    }

    pub fn run(&self, items: Vec<Item>, tx: Sender<Event>) {
        let mut made_backup = false;
        for (index, item) in items.iter().enumerate() {
            if !item.is_todo() {
                continue;
            }
            let _ = tx.send(Event::Start(index));

            if self.dry_run {
                let _ = tx.send(Event::Line(format!("would: {}", item.title)));
                let _ = tx.send(Event::Finish(index, Ok(())));
                continue;
            }

            if item.root && !probe::run_ok("sudo -n true >/dev/null 2>&1") {
                let _ = tx.send(Event::NeedSudo);
            }

            let outcome = match &item.action {
                Action::Packages { packages, aur, .. } => self.packages(packages, *aur, &tx),
                Action::Link(link) => {
                    let result = self.link(link, &tx);
                    made_backup |= result.as_ref().map(|b| *b).unwrap_or(false);
                    result.map(|_| ())
                }
                Action::Setting(setting) => self.setting(setting, &tx),
                Action::Step(step) => {
                    let mut result = Ok(());
                    for line in &step.run {
                        result = self.shell(line, step.root, &tx);
                        if result.is_err() {
                            break;
                        }
                    }
                    result
                }
            };

            let _ = tx.send(Event::Finish(index, outcome));
        }
        let _ = tx.send(Event::AllDone(made_backup.then(|| self.backup.clone())));
    }

    // ---- the four kinds of work -----------------------------------------

    fn packages(&self, packages: &[crate::data::Package], aur: bool, tx: &Sender<Event>) -> Result<(), String> {
        if packages.is_empty() {
            return Ok(());
        }
        let names: Vec<String> = packages.iter().map(|p| probe::shell_quote(&p.name)).collect();
        let cmd = if aur {
            let helper = ["yay", "paru", "pikaur", "trizen"]
                .iter()
                .find(|h| probe::which(h))
                .ok_or_else(|| "no AUR helper installed".to_string())?;
            // --needed so a re-run is a no-op rather than a reinstall.
            format!("{helper} -S --needed --noconfirm {}", names.join(" "))
        } else {
            format!("sudo pacman -S --needed --noconfirm {}", names.join(" "))
        };
        self.shell(&cmd, false, tx)
    }

    /// Returns whether this run wrote anything into the backup directory -
    /// either a file moved aside or a note of a file created.
    fn link(&self, link: &crate::data::Link, tx: &Sender<Event>) -> Result<bool, String> {
        let source = self.repo.join(&link.repo);
        let target = data::expand(&link.target);
        let mut backed_up = false;

        if let Some(parent) = target.parent() {
            std::fs::create_dir_all(parent).map_err(|e| format!("{}: {e}", parent.display()))?;
        }

        // Anything already there that is not our link is moved aside, keeping
        // its path under the backup root so --restore can put it back exactly.
        if std::fs::symlink_metadata(&target).is_ok() {
            // Anything outside home (/etc, /usr) keeps its shape under the
            // backup root instead of escaping it: joining an absolute path
            // would throw the root away.
            let relative = target
                .strip_prefix(data::expand("~"))
                .unwrap_or_else(|_| target.strip_prefix("/").unwrap_or(&target));
            let saved = self.backup.join(relative);
            if saved == target {
                return Err(format!(
                    "refusing to back {} up onto itself",
                    target.display()
                ));
            }
            if let Some(parent) = saved.parent() {
                std::fs::create_dir_all(parent)
                    .map_err(|e| format!("{}: {e}", parent.display()))?;
            }
            std::fs::rename(&target, &saved)
                .map_err(|e| format!("moving {} aside: {e}", target.display()))?;
            let _ = tx.send(Event::Line(format!(
                "backed up {} -> {}",
                target.display(),
                saved.display()
            )));
            backed_up = true;
        }

        let mut touched = backed_up;
        if !backed_up {
            // Nothing was here, so restoring means removing what we are about
            // to put here - which needs remembering now, while we know it.
            touched |= self.record_created(&link.kind, &target, &source);
        }

        if link.kind == "copy" {
            self.shell(
                &format!(
                    "cp -a {} {}",
                    probe::shell_quote(&source.to_string_lossy()),
                    probe::shell_quote(&target.to_string_lossy())
                ),
                false,
                tx,
            )?;
        } else {
            symlink(&source, &target)
                .map_err(|e| format!("linking {}: {e}", target.display()))?;
            let _ = tx.send(Event::Line(format!(
                "{} -> {}",
                target.display(),
                source.display()
            )));
        }
        Ok(touched)
    }

    /// Append one created path to the manifest. Best effort: failing to note
    /// a file down must not fail the install that created it.
    fn record_created(&self, kind: &str, target: &Path, source: &Path) -> bool {
        use std::io::Write;
        if std::fs::create_dir_all(&self.backup).is_err() {
            return false;
        }
        if let Ok(mut file) = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(self.backup.join(MANIFEST))
        {
            return writeln!(
                file,
                "{kind}\t{}\t{}",
                target.display(),
                source.display()
            )
            .is_ok();
        }
        false
    }

    fn setting(&self, setting: &Setting, tx: &Sender<Event>) -> Result<(), String> {
        let cmd = match setting.tool.as_str() {
            "gsettings" => format!(
                "gsettings set {} {}",
                setting.key,
                probe::shell_quote(&setting.value)
            ),
            "xfconf" => {
                // The type matters: writing "true" into a boolean property as
                // a string leaves Thunar reading a string where it wants a
                // bool, and the setting silently does nothing.
                let (channel, property) = setting
                    .key
                    .split_once(char::is_whitespace)
                    .ok_or_else(|| format!("xfconf key needs `channel /property`: {}", setting.key))?;
                let kind = match setting.value.as_str() {
                    "true" | "false" => "bool",
                    v if !v.is_empty() && v.chars().all(|c| c.is_ascii_digit()) => "int",
                    _ => "string",
                };
                format!(
                    "xfconf-query -c {} -p {} -n -t {kind} -s {}",
                    probe::shell_quote(channel.trim()),
                    probe::shell_quote(property.trim()),
                    probe::shell_quote(&setting.value)
                )
            }
            other => return Err(format!("unknown setting tool: {other}")),
        };
        // xfconf talks to xfconfd over the SESSION bus, and there is no session
        // bus when the installer runs from a TTY before the first login - which
        // is exactly when phase 1 runs. Every one of the 30 thunar/xsettings
        // values failed that way on a bare machine. dbus-run-session gives the
        // command a bus of its own; xfconfd still writes the same
        // xfce-perchannel-xml file, so the value survives the bus it was set on.
        let cmd = if setting.tool == "xfconf"
            && std::env::var("DBUS_SESSION_BUS_ADDRESS").is_err()
            && probe::which("dbus-run-session")
        {
            format!("dbus-run-session -- {cmd}")
        } else {
            cmd
        };
        self.shell(&cmd, false, tx)
    }

    /// Run one command, streaming its output. stderr is merged into stdout so
    /// the log reads in the order things actually happened.
    fn shell(&self, cmd: &str, _root: bool, tx: &Sender<Event>) -> Result<(), String> {
        let _ = tx.send(Event::Line(format!("$ {cmd}")));
        // stderr is merged into stdout by the shell rather than piped
        // separately. Two pipes drained one after the other deadlock the
        // moment the second one fills - pacman writes progress to one and
        // warnings to the other, so it would have hung on a real install.
        let mut child = Command::new("sh")
            .arg("-c")
            .arg(format!("{cmd} 2>&1"))
            .current_dir(&self.repo)
            .envs(self.answers.iter().map(|(k, v)| (k.as_str(), v.as_str())))
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|e| format!("spawning: {e}"))?;

        if let Some(out) = child.stdout.take() {
            for line in BufReader::new(out).lines().map_while(Result::ok) {
                let _ = tx.send(Event::Line(line));
            }
        }
        match child.wait() {
            Ok(status) if status.success() => Ok(()),
            Ok(status) => Err(format!("exited {}", status.code().unwrap_or(-1))),
            Err(e) => Err(format!("waiting: {e}")),
        }
    }
}

/// What `restore` did, so the caller can say it plainly.
pub struct Restored {
    /// Originals moved back to where they were.
    pub files: usize,
    /// Links and copies this installer created, now taken away again.
    pub removed: usize,
    /// Created paths left alone because they had been changed since.
    pub kept: Vec<PathBuf>,
}

/// Put back everything the most recent run moved aside, and take away what it
/// created where nothing had been.
pub fn restore(backup_root: &Path) -> Result<Restored, String> {
    let home = data::expand("~");
    let mut restored = 0;
    let mut stack = vec![backup_root.to_path_buf()];
    while let Some(dir) = stack.pop() {
        for entry in std::fs::read_dir(&dir).map_err(|e| e.to_string())?.flatten() {
            let path = entry.path();
            let relative = path.strip_prefix(backup_root).unwrap_or(&path);
            if relative == Path::new(MANIFEST) {
                continue; // our own bookkeeping, not a saved file
            }
            let target = home.join(relative);
            // A real directory in the backup is descended into: only the
            // files inside it were moved, not the directory itself.
            if path.is_dir() && !path.is_symlink() {
                stack.push(path);
                continue;
            }
            // Whatever we put there goes; the saved original takes its place.
            if let Ok(meta) = std::fs::symlink_metadata(&target) {
                if meta.is_dir() && !meta.file_type().is_symlink() {
                    let _ = std::fs::remove_dir_all(&target);
                } else {
                    let _ = std::fs::remove_file(&target);
                }
            }
            if let Some(parent) = target.parent() {
                let _ = std::fs::create_dir_all(parent);
            }
            std::fs::rename(&path, &target).map_err(|e| e.to_string())?;
            restored += 1;
        }
    }
    let (removed, kept) = undo_created(backup_root);
    Ok(Restored { files: restored, removed, kept })
}

/// Remove the files the run created - but only the ones still exactly as it
/// left them. A symlink the user has since repointed, or a copy they have
/// edited, is theirs now and stays, named in the return value so they hear
/// about it rather than silently keeping a file they think is gone.
fn undo_created(backup_root: &Path) -> (usize, Vec<PathBuf>) {
    let Ok(manifest) = std::fs::read_to_string(backup_root.join(MANIFEST)) else {
        return (0, Vec::new());
    };
    let (mut removed, mut kept) = (0, Vec::new());
    for line in manifest.lines() {
        let mut fields = line.split('\t');
        let (Some(kind), Some(target), Some(source)) =
            (fields.next(), fields.next(), fields.next())
        else {
            continue;
        };
        let (target, source) = (PathBuf::from(target), PathBuf::from(source));
        let ours = match kind {
            "copy" => match (std::fs::read(&target), std::fs::read(&source)) {
                (Ok(a), Ok(b)) => a == b,
                _ => false,
            },
            _ => std::fs::read_link(&target).map(|t| t == source).unwrap_or(false),
        };
        if !ours {
            if std::fs::symlink_metadata(&target).is_ok() {
                kept.push(target);
            }
            continue;
        }
        if std::fs::remove_file(&target).is_ok() {
            removed += 1;
        }
    }
    (removed, kept)
}
