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
    AllDone(RunReport),
    /// Root is needed and the cached credential has expired.
    NeedSudo,
}

#[derive(Default, Debug)]
pub struct RunReport {
    pub backup: Option<PathBuf>,
    pub required_failures: usize,
    pub optional_failures: usize,
    pub required_pending: usize,
    pub staged_session: usize,
}

impl RunReport {
    pub fn success(&self) -> bool {
        self.required_failures == 0 && self.required_pending == 0
    }
}

// Visit explicit prerequisites before their consumers. Invalid graphs fail
// closed per item, including cycles and references to unselected steps.
fn execution_order(items: &[Item]) -> Vec<(usize, Result<(), String>)> {
    fn visit(
        i: usize,
        items: &[Item],
        marks: &mut [u8],
        out: &mut Vec<(usize, Result<(), String>)>,
    ) -> Result<(), String> {
        if marks[i] == 2 {
            return Ok(());
        }
        if marks[i] == 1 {
            return Err("dependency cycle".into());
        }
        marks[i] = 1;
        let mut result = Ok(());
        let dependencies: Vec<&str> = match &items[i].action {
            Action::Step(step) => step.after.iter().map(String::as_str).collect(),
            Action::Packages { aur, .. } => [
                "system-update",
                if *aur { "aur-helper" } else { "system-update" },
            ]
            .into_iter()
            .filter(|id| {
                items
                    .iter()
                    .any(|item| matches!(&item.action, Action::Step(s) if s.id == *id))
            })
            .collect(),
            _ => vec![],
        };
        {
            for dep in dependencies {
                match items
                    .iter()
                    .position(|item| matches!(&item.action, Action::Step(s) if s.id == dep))
                {
                    Some(j) => {
                        if let Err(why) = visit(j, items, marks, out) {
                            result = Err(why);
                        }
                    }
                    None => result = Err(format!("missing dependency: {dep}")),
                }
            }
        }
        marks[i] = 2;
        out.push((i, result.clone()));
        result
    }
    let mut out = Vec::new();
    let mut marks = vec![0; items.len()];
    for i in 0..items.len() {
        let _ = visit(i, items, &mut marks, &mut out);
    }
    out
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
    /// Credentials, applied at the END of the run: an `apply` needs the tools
    /// the run installs (the opencode key goes in with `fish -c`, and on a
    /// bare machine fish does not exist until the core group is in).
    pub secrets: Vec<(crate::data::Question, String)>,
}

impl Runner {
    pub fn new(repo: PathBuf, dry_run: bool) -> Self {
        let stamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);
        let backup = data::expand("~/.local/state/blackwall/backups").join(format!("{stamp}"));
        Self {
            repo,
            dry_run,
            backup,
            answers: Vec::new(),
            secrets: Vec::new(),
        }
    }

    pub fn with_answers(mut self, answers: Vec<(String, String)>) -> Self {
        self.answers = answers;
        self
    }

    pub fn with_secrets(mut self, secrets: Vec<(crate::data::Question, String)>) -> Self {
        self.secrets = secrets;
        self
    }

    /// Put one credential where it belongs, without it passing through a
    /// command line.
    ///
    /// The value goes in on STDIN and the question's `apply` reads it from
    /// there. It is never an argument (arguments are visible in `ps` to every
    /// process on the machine), never an environment variable handed to
    /// unrelated steps, and never echoed - the log gets the question's title
    /// and nothing else.
    pub fn apply_secret(&self, question: &crate::data::Question, value: &str, tx: &Sender<Event>) {
        use std::io::Write;

        if question.apply.trim().is_empty() {
            let _ = tx.send(Event::Line(format!(
                "no way to store {} - nothing written",
                question.env
            )));
            return;
        }
        let _ = tx.send(Event::Line(format!("storing {}", question.env)));
        if self.dry_run {
            return;
        }
        let child = Command::new("sh")
            .arg("-c")
            .arg(&question.apply)
            .current_dir(&self.repo)
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn();
        match child {
            Ok(mut child) => {
                if let Some(mut stdin) = child.stdin.take() {
                    // With a newline: `read` is the obvious way for an `apply`
                    // to take the value, and it returns non-zero on a line
                    // that ends at EOF instead - so a perfectly good
                    // credential was reported as "could not store".
                    let _ = stdin.write_all(value.as_bytes());
                    let _ = stdin.write_all(b"\n");
                }
                match child.wait() {
                    Ok(status) if status.success() => {
                        let _ = tx.send(Event::Line(format!("{} stored", question.env)));
                    }
                    _ => {
                        let _ = tx.send(Event::Line(format!(
                            "could not store {} - set it by hand",
                            question.env
                        )));
                    }
                }
            }
            Err(e) => {
                let _ = tx.send(Event::Line(format!("storing {}: {e}", question.env)));
            }
        }
    }

    pub fn run(mut self, items: Vec<Item>, tx: Sender<Event>) {
        // The deferred helper reads the catalogue again, so carry forward
        // the exact exclusions approved on the review screen.
        let skipped = items
            .iter()
            .filter_map(|item| match (&item.action, &item.state) {
                (Action::Step(step), crate::plan::State::Skipped) => Some(step.id.as_str()),
                _ => None,
            })
            .collect::<Vec<_>>()
            .join(",");
        self.answers
            .push(("BLACKWALL_INSTALL_SKIPPED_STEPS".into(), skipped));
        let mut made_backup = false;
        let mut report = RunReport::default();
        let mut succeeded: Vec<bool> = items
            .iter()
            .map(|i| i.state == crate::plan::State::Satisfied)
            .collect();
        for (index, graph_result) in execution_order(&items) {
            let item = &items[index];
            if !item.is_todo() {
                if item.required && !succeeded[index] {
                    if matches!(item.state, crate::plan::State::Failed(_)) {
                        report.required_failures += 1;
                    } else if !matches!(item.state, crate::plan::State::Deferred(_)) {
                        report.required_pending += 1;
                    }
                }
                continue;
            }
            let _ = tx.send(Event::Start(index));
            let dependency_result = graph_result.and_then(|_| {
                if let Action::Step(step) = &item.action {
                    for dep in &step.after {
                        let ready = items.iter().enumerate().any(|(j, candidate)| {
                            matches!(&candidate.action, Action::Step(s) if &s.id == dep)
                                && succeeded[j]
                        });
                        if !ready {
                            return Err(format!("dependency did not succeed: {dep}"));
                        }
                    }
                }
                if let Action::Packages { aur, .. } = &item.action {
                    for dep in [
                        "system-update",
                        if *aur { "aur-helper" } else { "system-update" },
                    ] {
                        if let Some(j) = items.iter().position(
                            |candidate| matches!(&candidate.action, Action::Step(s) if s.id == dep),
                        ) {
                            if !succeeded[j] {
                                return Err(format!("dependency did not succeed: {dep}"));
                            }
                        }
                    }
                }
                Ok(())
            });
            if let Err(why) = dependency_result {
                if item.required {
                    report.required_failures += 1;
                } else {
                    report.optional_failures += 1;
                }
                let _ = tx.send(Event::Finish(index, Err(why)));
                continue;
            }

            if self.dry_run {
                succeeded[index] = true;
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

            succeeded[index] = outcome.is_ok();
            if outcome.is_err() {
                if item.required {
                    report.required_failures += 1;
                } else {
                    report.optional_failures += 1;
                }
            }
            let _ = tx.send(Event::Finish(index, outcome));
        }
        // Required session work is complete only as an explicitly prepared
        // first-login job; an arbitrary deferred row is never success.
        let session_prepared = items.iter().enumerate().any(|(i, item)| {
            matches!(&item.action, Action::Step(step) if step.id == "session-prepare")
                && succeeded[i]
        });
        for item in &items {
            if matches!(item.state, crate::plan::State::Deferred(_)) {
                let prepared = session_prepared
                    && matches!(&item.action, Action::Step(step) if step.auto_session());
                if prepared {
                    report.staged_session += 1;
                } else if item.required {
                    report.required_pending += 1;
                }
            }
        }
        // Last, not first. On a bare machine the first attempt ran before
        // pacman had installed fish, and the opencode key was reported as
        // "could not store" because the command that stores it did not exist.
        for (question, value) in &self.secrets {
            self.apply_secret(question, value, &tx);
        }
        report.backup = made_backup.then(|| self.backup.clone());
        let _ = tx.send(Event::AllDone(report));
    }

    // ---- the four kinds of work -----------------------------------------

    fn packages(
        &self,
        packages: &[crate::data::Package],
        aur: bool,
        tx: &Sender<Event>,
    ) -> Result<(), String> {
        if packages.is_empty() {
            return Ok(());
        }
        let names: Vec<String> = packages
            .iter()
            .map(|p| probe::shell_quote(&p.name))
            .collect();

        if !aur {
            // The official repositories are one transaction: pacman resolves
            // the whole set together, and a name that does not exist is a
            // mistake in the catalogue, not a flaky build.
            return self.shell(
                &format!("sudo pacman -S --needed --noconfirm {}", names.join(" ")),
                false,
                tx,
            );
        }

        let helper = ["yay", "paru", "pikaur", "trizen"]
            .iter()
            .find(|h| probe::which(h))
            .ok_or_else(|| "no AUR helper installed".to_string())?;

        // ONE AT A TIME, on purpose. `yay -S a b c` builds them all and then
        // installs them in a single transaction, so one package that fails to
        // build takes the others down with it. That is not hypothetical: on a
        // bare Arch container `wallust` failed its own checksum, and eww and
        // wlogout - both of which had built successfully - were never
        // installed. The AUR is other people's PKGBUILDs; one of them being
        // broken today must cost that package, not the rice.
        let mut failed: Vec<String> = Vec::new();
        for (package, quoted) in packages.iter().zip(names.iter()) {
            // --needed so a re-run is a no-op rather than a reinstall.
            let cmd = format!("{helper} -S --needed --noconfirm {quoted}");
            if self.shell(&cmd, false, tx).is_err() {
                failed.push(package.name.clone());
                let _ = tx.send(Event::Line(format!(
                    "!! {} did not install; continuing with the rest",
                    package.name
                )));
            }
        }
        if failed.is_empty() {
            Ok(())
        } else {
            Err(format!(
                "could not install from the AUR: {}",
                failed.join(" ")
            ))
        }
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
            symlink(&source, &target).map_err(|e| format!("linking {}: {e}", target.display()))?;
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
            return writeln!(file, "{kind}\t{}\t{}", target.display(), source.display()).is_ok();
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
                let (channel, property) =
                    setting.key.split_once(char::is_whitespace).ok_or_else(|| {
                        format!("xfconf key needs `channel /property`: {}", setting.key)
                    })?;
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
        // BOTH tools need a session bus, and there is none when phase 1 runs
        // from a TTY before the first login.
        //
        // xfconf at least fails loudly - all 30 thunar/xsettings values errored
        // on a bare machine. gsettings is worse: dconf prints
        //
        //   dconf-WARNING: failed to commit changes to dconf:
        //   Cannot autolaunch D-Bus without X11 $DISPLAY
        //
        // and `gsettings set` still exits 0, so every one of the 25 values
        // reported success and wrote nothing. That is the failure this whole
        // installer is built to avoid.
        //
        // dbus-run-session gives the command a bus of its own. Both daemons
        // write to the same file they always write to - dconf's user database,
        // xfconfd's xfce-perchannel-xml - so the value outlives the bus.
        let cmd = format!("{}{cmd}", probe::session_bus_prefix());
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
        for entry in std::fs::read_dir(&dir)
            .map_err(|e| e.to_string())?
            .flatten()
        {
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
    Ok(Restored {
        files: restored,
        removed,
        kept,
    })
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
            _ => std::fs::read_link(&target)
                .map(|t| t == source)
                .unwrap_or(false),
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::data::Step;
    use crate::plan::State;

    fn step(id: &str, after: &[&str], command: &str) -> Item {
        Item {
            title: id.into(),
            detail: String::new(),
            root: false,
            required: true,
            action: Action::Step(Step {
                id: id.into(),
                title: id.into(),
                run: vec![command.into()],
                check: String::new(),
                root: false,
                needs_session: false,
                interactive: false,
                optional: false,
                first: false,
                after: after.iter().map(|s| s.to_string()).collect(),
                note: String::new(),
                group: String::new(),
            }),
            state: State::Todo,
        }
    }

    fn events(items: Vec<Item>, dry_run: bool) -> Vec<Event> {
        let (tx, rx) = std::sync::mpsc::channel();
        Runner::new(std::env::temp_dir(), dry_run).run(items, tx);
        rx.into_iter().collect()
    }

    #[test]
    fn dependency_runs_before_dependent_even_when_catalogue_is_reordered() {
        let result = events(
            vec![
                step("child", &["parent"], "true"),
                step("parent", &[], "true"),
            ],
            false,
        );
        let starts: Vec<_> = result
            .iter()
            .filter_map(|e| {
                if let Event::Start(i) = e {
                    Some(*i)
                } else {
                    None
                }
            })
            .collect();
        assert_eq!(starts, vec![1, 0]);
    }

    #[test]
    fn failed_dependency_blocks_command() {
        let result = events(
            vec![
                step("parent", &[], "false"),
                step("child", &["parent"], "true"),
            ],
            false,
        );
        assert!(result
            .iter()
            .any(|e| matches!(e, Event::Finish(1, Err(why)) if why.contains("dependency"))));
    }

    #[test]
    fn missing_dependency_and_cycle_fail_closed_even_in_dry_run() {
        for items in [
            vec![step("child", &["missing"], "true")],
            vec![step("a", &["b"], "true"), step("b", &["a"], "true")],
        ] {
            let result = events(items, true);
            assert!(result.iter().any(|e| matches!(e, Event::Finish(_, Err(_)))));
        }
    }
    fn report(items: Vec<Item>) -> RunReport {
        events(items, false)
            .into_iter()
            .find_map(|e| match e {
                Event::AllDone(report) => Some(report),
                _ => None,
            })
            .unwrap()
    }

    #[test]
    fn optional_failure_warns_but_required_failure_rejects_completion() {
        let mut optional = step("optional", &[], "false");
        optional.required = false;
        let warning = report(vec![optional]);
        assert!(warning.success());
        assert_eq!(warning.optional_failures, 1);
        assert!(!report(vec![step("required", &[], "false")]).success());
    }

    #[test]
    fn skipping_or_deferring_required_work_is_not_success() {
        for state in [State::Skipped, State::Deferred("needs session".into())] {
            let mut item = step("required", &[], "true");
            item.state = state;
            assert!(!report(vec![item]).success());
        }
    }

    #[test]
    fn session_jobs_are_staged_only_when_prepare_succeeds() {
        for command in ["true", "false"] {
            let mut session = step("session", &[], "true");
            session.state = State::Deferred("needs session".into());
            if let Action::Step(step) = &mut session.action {
                step.needs_session = true;
            }
            let report = report(vec![session, step("session-prepare", &[], command)]);
            assert_eq!(report.success(), command == "true");
            assert_eq!(report.staged_session, usize::from(command == "true"));
        }
    }

    #[test]
    fn user_skipped_prerequisite_does_not_allow_dependent() {
        let mut parent = step("parent", &[], "true");
        parent.state = State::Skipped;
        let result = events(vec![parent, step("child", &["parent"], "true")], false);
        assert!(result.iter().any(|e| matches!(e, Event::Finish(1, Err(_)))));
    }
    #[test]
    fn manual_only_session_work_is_not_counted_as_staged() {
        for name in ["selftest", "privileged"] {
            let mut item = step(name, &[], "true");
            item.required = false;
            item.state = State::Deferred("needs session".into());
            if let Action::Step(step) = &mut item.action {
                step.needs_session = true;
                step.root = name == "privileged";
            }
            let report = report(vec![item, step("session-prepare", &[], "true")]);
            assert_eq!(report.staged_session, 0);
        }
    }

    #[test]
    fn reviewed_skipped_steps_are_exported_to_registration() {
        let mut skipped = step("hyprglass", &[], "true");
        skipped.required = false;
        skipped.state = State::Skipped;
        let report = report(vec![
            skipped,
            step(
                "session-prepare",
                &[],
                "test \"$BLACKWALL_INSTALL_SKIPPED_STEPS\" = hyprglass",
            ),
        ]);
        assert!(report.success());
    }
    #[test]
    fn required_interactive_session_job_is_pending_not_staged() {
        let mut item = step("interactive", &[], "true");
        item.state = State::Deferred("needs session".into());
        if let Action::Step(step) = &mut item.action {
            step.needs_session = true;
            step.interactive = true;
        }
        let report = report(vec![item, step("session-prepare", &[], "true")]);
        assert!(!report.success());
        assert_eq!(report.required_pending, 1);
        assert_eq!(report.staged_session, 0);
    }
}
