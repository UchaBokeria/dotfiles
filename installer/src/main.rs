//! blackwall-install - put this rice on a machine.
//!
//! The shape of it: probe the machine, ask what the person wants, show the
//! whole plan, and only then touch anything. Every item in the plan carries
//! why it is there and what state the machine is already in, so running this
//! on a half-installed box proposes only the remainder.
//!
//! It is launched by `./install` at the repo root, which makes sure there is a
//! Rust toolchain, builds this, and hands over.

mod banner;
mod data;
mod exec;
mod plan;
mod probe;
mod theme;
mod ui;

use std::collections::{HashMap, VecDeque};
use std::io::stdout;
use std::path::PathBuf;
use std::sync::mpsc::{self, Receiver};
use std::time::{Duration, Instant};

use anyhow::Result;
use crossterm::event::{self, Event as TermEvent, KeyCode, KeyEventKind};
use crossterm::execute;
use crossterm::terminal::{
    disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen,
};
use ratatui::backend::CrosstermBackend;
use ratatui::Terminal;

use data::Catalogue;
use plan::{Item, Selections, State};
use probe::System;

#[derive(PartialEq, Clone, Copy)]
pub enum Screen {
    Welcome,
    Groups,
    Questions,
    Wallpaper,
    Plan,
    Running,
    Done,
}

pub struct App {
    pub screen: Screen,
    pub frame: usize,
    pub cursor: usize,
    pub selected: Vec<String>,
    pub catalogue: Catalogue,
    pub system: System,
    pub items: Vec<Item>,
    pub log: VecDeque<String>,
    pub current: String,
    pub finished: usize,
    pub todo_total: usize,
    pub dry_run: bool,
    pub personal: bool,
    pub backup: Option<PathBuf>,
    pub report: Option<exec::RunReport>,
    pub started: Instant,
    pub repo: PathBuf,
    /// Catalogue entries this clone does not have. A fresh clone missing a
    /// file is the failure mode of a rice kept on one machine.
    pub missing_sources: Vec<String>,
    /// Images in `wallpapers/`, and which one is chosen.
    pub wallpapers: Vec<String>,
    pub wallpaper: usize,
    /// Plan items the user skipped with space, with the state to restore.
    pub user_skipped: HashMap<usize, State>,
    /// One chosen option index per question, and the answers they resolve to.
    pub answer_at: Vec<usize>,
    pub answers: Vec<(String, String)>,
    /// What has been typed into each free-text question, by index.
    pub typed: HashMap<usize, String>,
    rx: Option<Receiver<exec::Event>>,
    quit: bool,
}

impl App {
    fn new(
        repo: PathBuf,
        catalogue: Catalogue,
        system: System,
        dry_run: bool,
        missing_sources: Vec<String>,
    ) -> Self {
        // Optional groups start unticked: an installer that pre-selects
        // everything is asking for a yes it has not earned.
        Self {
            screen: Screen::Welcome,
            frame: 0,
            cursor: 0,
            selected: Vec::new(),
            catalogue,
            system,
            items: Vec::new(),
            log: VecDeque::with_capacity(512),
            current: String::new(),
            finished: 0,
            todo_total: 0,
            dry_run,
            personal: false,
            backup: None,
            report: None,
            started: Instant::now(),
            repo,
            wallpapers: Vec::new(),
            wallpaper: 0,
            user_skipped: HashMap::new(),
            answer_at: Vec::new(),
            answers: Vec::new(),
            typed: HashMap::new(),
            missing_sources,
            rx: None,
            quit: false,
        }
    }

    /// Run every question's `detect`, and start each one on the option that
    /// matches what was found. A question whose answer the machine already
    /// knows should open on that answer, not on the first line of a list.
    fn resolve_questions(&mut self) {
        if !self.answer_at.is_empty() {
            return;
        }
        for question in &self.catalogue.questions.questions {
            let found = std::env::var(&question.env)
                .ok()
                .filter(|value| !value.is_empty())
                .or_else(|| {
                    if self.dry_run || question.detect.is_empty() {
                        None
                    } else {
                        probe::capture(&question.detect).map(|o| o.trim().to_string())
                    }
                });
            let value = match found {
                Some(v) if !v.is_empty() => v,
                _ => question.default.clone(),
            };
            let index = self.answer_at.len();
            if question.secret {
                // A scripted install has no one to type at it. An exported
                // variable of the same name is taken as the answer - it came
                // from the person running this either way, and it still goes
                // in through stdin rather than a command line.
                if let Ok(from_env) = std::env::var(&question.env) {
                    if !from_env.is_empty() {
                        self.typed.insert(index, from_env);
                    }
                }
            } else if question.options.is_empty() && !value.is_empty() {
                self.typed.insert(index, value.clone());
            }
            let at = question
                .options
                .iter()
                .position(|o| o.value == value)
                .unwrap_or(0);
            self.answer_at.push(at);
        }
        self.collect_answers();
    }

    fn collect_answers(&mut self) {
        self.answers = self
            .catalogue
            .questions
            .questions
            .iter()
            .enumerate()
            .filter(|(_, q)| !q.secret)
            .map(|(i, q)| {
                let value = if q.options.is_empty() {
                    self.typed
                        .get(&i)
                        .cloned()
                        .unwrap_or_else(|| q.default.clone())
                } else {
                    q.options
                        .get(self.answer_at.get(i).copied().unwrap_or(0))
                        .map(|o| o.value.clone())
                        .unwrap_or_else(|| q.default.clone())
                };
                (q.env.clone(), value)
            })
            .collect();
        self.answers
            .push(("BLACKWALL_INSTALL_GROUPS".into(), self.selected.join(",")));
    }

    pub fn elapsed(&self) -> String {
        let secs = self.started.elapsed().as_secs();
        format!("{}m{:02}s", secs / 60, secs % 60)
    }

    fn rebuild_plan(&mut self) {
        let sel = Selections {
            groups: self.selected.clone(),
            personal: self.personal,
            wallpaper: self.wallpapers.get(self.wallpaper).cloned(),
            answers: self.answers.clone(),
            dry_run: self.dry_run,
        };
        self.user_skipped.clear();
        self.items = plan::build(&self.catalogue, &sel, &self.system, &self.repo);
        self.todo_total = self.items.iter().filter(|i| i.is_todo()).count();
        self.cursor = 0;
    }

    fn start_run(&mut self) {
        let (tx, rx) = mpsc::channel();
        self.rx = Some(rx);
        self.screen = Screen::Running;
        self.started = Instant::now();
        self.finished = 0;
        let runner = exec::Runner::new(self.repo.clone(), self.dry_run)
            .with_answers(self.answers.clone())
            .with_secrets(self.secrets());
        let items = self.items.clone();
        std::thread::spawn(move || runner.run(items, tx));
    }

    fn drain(&mut self) {
        // Collected first, handled second: handling an event can clear
        // `self.rx` (AllDone does), and that cannot happen while the receiver
        // is still borrowed.
        let mut events = Vec::new();
        let mut disconnected = false;
        if let Some(rx) = &self.rx {
            // try_recv in a loop: the worker outruns the 100ms frame during a
            // noisy pacman transaction, and the log should not lag behind it.
            loop {
                match rx.try_recv() {
                    Ok(event) => events.push(event),
                    Err(mpsc::TryRecvError::Disconnected) => {
                        disconnected = true;
                        break;
                    }
                    Err(mpsc::TryRecvError::Empty) => break,
                }
            }
        }
        for event in events {
            match event {
                exec::Event::Line(line) => {
                    if self.log.len() == 512 {
                        self.log.pop_front();
                    }
                    self.log.push_back(line);
                }
                exec::Event::Start(index) => {
                    if let Some(item) = self.items.get_mut(index) {
                        item.state = State::Running;
                        self.current = item.title.clone();
                    }
                }
                exec::Event::Finish(index, result) => {
                    if let Some(item) = self.items.get_mut(index) {
                        item.state = match result {
                            Ok(()) => State::Done,
                            Err(why) => State::Failed(why),
                        };
                    }
                    self.finished += 1;
                }
                exec::Event::AllDone(report) => {
                    self.backup = report.backup.clone();
                    self.report = Some(report);
                    self.screen = Screen::Done;
                    self.rx = None;
                }
                exec::Event::NeedSudo => {
                    self.log.push_back(
                        "sudo credentials expired - run `sudo -v` in another terminal".into(),
                    );
                }
            }
        }
        if disconnected && self.report.is_none() {
            self.log
                .push_back("installer worker stopped before reporting completion".into());
            self.report = Some(exec::RunReport {
                required_failures: 1,
                ..Default::default()
            });
            self.screen = Screen::Done;
            self.rx = None;
        }
    }

    /// Is the question under the cursor one that is typed into rather than
    /// picked from? Up/down still move between questions; everything else on
    /// that row becomes text.
    fn cursor_is_text(&self) -> bool {
        self.catalogue
            .questions
            .questions
            .get(self.cursor)
            .map(|q| q.options.is_empty())
            .unwrap_or(false)
    }

    /// Credentials, as (question, value) for the ones actually answered.
    ///
    /// Kept apart from `answers` on purpose: these never become environment
    /// variables for arbitrary steps and never appear in a command line the
    /// log echoes. exec::Runner::apply_secret runs the question's own `apply`
    /// with the value on stdin.
    fn secrets(&self) -> Vec<(data::Question, String)> {
        self.catalogue
            .questions
            .questions
            .iter()
            .enumerate()
            .filter(|(_, q)| q.secret)
            .filter_map(|(i, q)| {
                let value = self.typed.get(&i)?;
                (!value.is_empty()).then(|| (q.clone(), value.clone()))
            })
            .collect()
    }

    fn cycle_answer(&mut self, by: isize) {
        let at = self.cursor;
        let Some(question) = self.catalogue.questions.questions.get(at) else {
            return;
        };
        let count = question.options.len();
        if count == 0 {
            return;
        }
        if let Some(slot) = self.answer_at.get_mut(at) {
            let next = (*slot as isize + by).rem_euclid(count as isize) as usize;
            *slot = next;
        }
        self.collect_answers();
    }

    fn key(&mut self, code: KeyCode) {
        let groups = self.catalogue.packages.groups.len();
        match self.screen {
            Screen::Welcome => match code {
                KeyCode::Enter => {
                    self.screen = Screen::Groups;
                    self.cursor = 0;
                }
                KeyCode::Char('q') => self.quit = true,
                _ => {}
            },
            Screen::Groups => match code {
                KeyCode::Up | KeyCode::Char('k') => self.cursor = self.cursor.saturating_sub(1),
                KeyCode::Down | KeyCode::Char('j') => {
                    self.cursor = (self.cursor + 1).min(groups.saturating_sub(1))
                }
                KeyCode::Char(' ') => {
                    if let Some(group) = self.catalogue.packages.groups.get(self.cursor) {
                        if !group.required {
                            let name = group.name.clone();
                            match self.selected.iter().position(|g| g == &name) {
                                Some(at) => {
                                    self.selected.remove(at);
                                }
                                None => self.selected.push(name),
                            }
                        }
                    }
                }
                KeyCode::Enter => {
                    self.resolve_questions();
                    self.screen = Screen::Questions;
                    self.cursor = 0;
                }
                KeyCode::Char('q') => self.quit = true,
                _ => {}
            },
            Screen::Questions => {
                let count = self.catalogue.questions.questions.len();
                match code {
                    KeyCode::Up => self.cursor = self.cursor.saturating_sub(1),
                    KeyCode::Down => self.cursor = (self.cursor + 1).min(count.saturating_sub(1)),
                    // A question with no options is typed into, so the keys
                    // that move between choices have to become characters.
                    KeyCode::Char(_) | KeyCode::Backspace if self.cursor_is_text() => match code {
                        KeyCode::Char(c) => {
                            self.typed.entry(self.cursor).or_default().push(c);
                            self.collect_answers();
                        }
                        KeyCode::Backspace => {
                            if let Some(v) = self.typed.get_mut(&self.cursor) {
                                v.pop();
                            }
                            self.collect_answers();
                        }
                        _ => {}
                    },
                    // left/right/space move through one question's choices.
                    KeyCode::Right | KeyCode::Char('l') | KeyCode::Char(' ') => {
                        self.cycle_answer(1);
                    }
                    KeyCode::Left | KeyCode::Char('h') => {
                        self.cycle_answer(-1);
                    }
                    KeyCode::Enter => {
                        self.collect_answers();
                        self.screen = Screen::Wallpaper;
                        self.cursor = self.wallpaper;
                    }
                    KeyCode::Esc => {
                        self.screen = Screen::Groups;
                        self.cursor = 0;
                    }
                    KeyCode::Char('q') => self.quit = true,
                    _ => {}
                }
            }
            Screen::Wallpaper => match code {
                KeyCode::Up | KeyCode::Char('k') => self.cursor = self.cursor.saturating_sub(1),
                KeyCode::Down | KeyCode::Char('j') => {
                    self.cursor = (self.cursor + 1).min(self.wallpapers.len().saturating_sub(1))
                }
                KeyCode::Enter => {
                    self.wallpaper = self.cursor;
                    self.rebuild_plan();
                    self.screen = Screen::Plan;
                }
                KeyCode::Esc => {
                    self.screen = Screen::Questions;
                    self.cursor = 0;
                }
                KeyCode::Char('q') => self.quit = true,
                _ => {}
            },
            Screen::Plan => match code {
                KeyCode::Up | KeyCode::Char('k') => self.cursor = self.cursor.saturating_sub(1),
                KeyCode::Down | KeyCode::Char('j') => {
                    self.cursor = (self.cursor + 1).min(self.items.len().saturating_sub(1))
                }
                KeyCode::Char('d') => {
                    self.dry_run = !self.dry_run;
                }
                // "Ask on conflicts": the plan lists every file in the way
                // before anything runs, and space takes any item out of it.
                KeyCode::Char(' ') => {
                    let at = self.cursor;
                    if let Some(prev) = self.user_skipped.remove(&at) {
                        if let Some(item) = self.items.get_mut(at) {
                            item.state = prev;
                        }
                    } else if let Some(item) = self.items.get_mut(at) {
                        if item.is_todo() {
                            self.user_skipped.insert(at, item.state.clone());
                            item.state = State::Skipped;
                        }
                    }
                    self.todo_total = self.items.iter().filter(|i| i.is_todo()).count();
                }
                KeyCode::Enter => self.start_run(),
                KeyCode::Esc => {
                    self.screen = Screen::Wallpaper;
                    self.cursor = self.wallpaper;
                }
                KeyCode::Char('q') => self.quit = true,
                _ => {}
            },
            Screen::Running => {
                // Keep the worker attached until it reports its result.
                // Exiting here used to silently leave child processes running.
            }
            Screen::Done => {
                if matches!(code, KeyCode::Char('q') | KeyCode::Enter | KeyCode::Esc) {
                    self.quit = true;
                }
            }
        }
    }
}

fn main() -> Result<()> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "-h" || a == "--help") {
        println!(
            "blackwall-install\n\n  \
             (no flags)     probe, ask, show the plan, install\n  \
             --dry-run      say what would happen, change nothing\n  \
             --restore DIR  put back what a previous run moved aside\n  \
             --snapshot S   print one screen as text (welcome|groups|questions|wallpaper|plan)\n  \
             --apply        run the plan without the TUI, for a tty-less shell\n  \
                            (repeat --group NAME to add optional groups)\n"
        );
        return Ok(());
    }

    if args.iter().any(|arg| arg == "--restore")
        && args
            .iter()
            .any(|arg| arg == "--dry-run" || arg == "--snapshot")
    {
        anyhow::bail!("cannot combine --restore with --dry-run or --snapshot");
    }

    let repo = repo_root();

    if let Some(at) = args.iter().position(|a| a == "--restore") {
        let dir = args
            .get(at + 1)
            .map(PathBuf::from)
            .or_else(latest_backup)
            .ok_or_else(|| anyhow::anyhow!("no backup directory given and none found"))?;
        let done = exec::restore(&dir).map_err(|e| anyhow::anyhow!(e))?;
        println!(
            "restored {} files from {}, removed {} the installer had added",
            done.files,
            dir.display(),
            done.removed
        );
        for kept in &done.kept {
            println!("  left alone (changed since): {}", kept.display());
        }
        return Ok(());
    }

    // A snapshot renders the same plan and questions as a preview: neither
    // arbitrary catalogue probes nor sudo credential probes may run.
    let dry_run = args.iter().any(|a| a == "--dry-run" || a == "--snapshot");
    let catalogue = Catalogue::load(&repo)?;
    let system = probe::probe(dry_run);
    let missing_sources = probe::missing_sources(&catalogue, &repo);
    let wallpapers = list_wallpapers(&repo);
    let mut app = App::new(repo, catalogue, system, dry_run, missing_sources);
    // Start on whatever this machine already uses, if it is one of ours.
    let current =
        std::fs::read_to_string(data::expand("~/.cache/last_wallpaper")).unwrap_or_default();
    app.wallpaper = wallpapers
        .iter()
        .position(|w| current.trim().ends_with(&format!("/{w}")))
        .or_else(|| wallpapers.iter().position(|w| w.starts_with("cyberpunk")))
        .unwrap_or(0);
    app.wallpapers = wallpapers;

    if args.iter().any(|a| a == "--apply") {
        let groups: Vec<String> = args
            .windows(2)
            .filter(|w| w[0] == "--group")
            .map(|w| w[1].clone())
            .collect();
        return apply(&mut app, groups);
    }

    if let Some(at) = args.iter().position(|a| a == "--snapshot") {
        let screen = args.get(at + 1).map(String::as_str).unwrap_or("welcome");
        return snapshot(&mut app, screen);
    }

    // A panic inside the alternate screen would otherwise leave the terminal
    // in raw mode with no echo, which looks like a hung machine.
    let hook = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        let _ = disable_raw_mode();
        let _ = execute!(stdout(), LeaveAlternateScreen);
        hook(info);
    }));

    enable_raw_mode()?;
    execute!(stdout(), EnterAlternateScreen)?;
    let mut terminal = Terminal::new(CrosstermBackend::new(stdout()))?;

    let result = run_loop(&mut terminal, &mut app);

    disable_raw_mode()?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen)?;
    terminal.show_cursor()?;
    result?;
    if app.report.as_ref().is_some_and(|r| !r.success()) {
        anyhow::bail!("required installation work failed or remains incomplete");
    }
    Ok(())
}

fn run_loop<B: ratatui::backend::Backend>(terminal: &mut Terminal<B>, app: &mut App) -> Result<()> {
    loop {
        terminal.draw(|f| ui::draw(f, app))?;
        app.drain();

        // 100ms: fast enough for the scanline to read as motion, slow enough
        // that a busy install does not spend its time redrawing.
        if event::poll(Duration::from_millis(100))? {
            if let TermEvent::Key(key) = event::read()? {
                if key.kind == KeyEventKind::Press {
                    app.key(key.code);
                }
            }
        }
        app.frame = app.frame.wrapping_add(1);
        if app.quit {
            return Ok(());
        }
    }
}

/// The repo is where `installer/data` lives. The wrapper exports it; when this
/// binary is run directly, walk up from the executable.
fn repo_root() -> PathBuf {
    if let Ok(root) = std::env::var("BLACKWALL_ROOT") {
        return PathBuf::from(root);
    }
    let mut dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(PathBuf::from))
        .unwrap_or_else(|| PathBuf::from("."));
    for _ in 0..6 {
        if dir.join("installer/data").is_dir() {
            return dir;
        }
        match dir.parent() {
            Some(parent) => dir = parent.to_path_buf(),
            None => break,
        }
    }
    std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

/// Build the plan and run it with no terminal at all.
///
/// The same `plan::build` and the same `exec::Runner` the TUI drives, so this
/// is how the runner gets tested end to end - and how the installer can be run
/// over ssh, or in a shell with no tty. Exit status is the number of failures.
fn apply(app: &mut App, groups: Vec<String>) -> Result<()> {
    app.selected = groups;
    // Headless runs get the same detection the questions screen does. Without
    // this the answers were empty and every step fell back to the literal
    // default in its own `${BLACKWALL_x:-...}`, so --apply on an AMD machine
    // wrote the Intel driver into machine.lua. An answer already in the
    // environment still wins: the shell's value is what the step reads.
    app.resolve_questions();
    app.rebuild_plan();

    let titles: Vec<String> = app.items.iter().map(|i| i.title.clone()).collect();
    println!("{}", plan::summary(&app.items));
    for item in &app.items {
        match &item.state {
            State::Failed(why) => println!(
                "   FAILED ({}): {} - {why}",
                if item.required {
                    "required"
                } else {
                    "optional"
                },
                item.title
            ),
            State::Deferred(why) => println!("   DEFERRED: {} - {why}", item.title),
            State::Skipped if item.required => println!("   SKIPPED (required): {}", item.title),
            _ => {}
        }
    }
    for (key, value) in &app.answers {
        if std::env::var(key).is_err() {
            println!("   {key}={value}   (detected)");
        }
    }
    if app.dry_run {
        println!("dry run: nothing will change");
    }

    let (tx, rx) = mpsc::channel();
    // Anything already exported wins; the detected value fills the rest.
    let answers: Vec<(String, String)> = app
        .answers
        .iter()
        .filter(|(k, _)| std::env::var(k).is_err())
        .cloned()
        .collect();
    let runner = exec::Runner::new(app.repo.clone(), app.dry_run)
        .with_answers(answers)
        .with_secrets(app.secrets());
    let items = app.items.clone();
    let worker = std::thread::spawn(move || runner.run(items, tx));

    let mut report = None;
    for event in rx {
        match event {
            exec::Event::Start(index) => {
                println!("\n=> {}", titles.get(index).cloned().unwrap_or_default())
            }
            exec::Event::Line(line) => println!("   {line}"),
            exec::Event::Finish(index, Err(why)) => {
                println!(
                    "   FAILED ({}): {} - {why}",
                    if app.items.get(index).is_some_and(|item| item.required) {
                        "required"
                    } else {
                        "optional"
                    },
                    titles.get(index).cloned().unwrap_or_default()
                );
            }
            exec::Event::Finish(_, Ok(())) => {}
            exec::Event::NeedSudo => println!("   (sudo credentials have expired)"),
            exec::Event::AllDone(done) => {
                if let Some(dir) = &done.backup {
                    println!(
                        "\nundo this run with: ./install --restore {}",
                        dir.display()
                    );
                }
                report = Some(done);
            }
        }
    }
    worker
        .join()
        .map_err(|_| anyhow::anyhow!("installer worker stopped unexpectedly"))?;
    let report = report.ok_or_else(|| anyhow::anyhow!("installer did not report completion"))?;
    println!(
        "\n{} required failures, {} optional failures, {} required pending",
        report.required_failures, report.optional_failures, report.required_pending
    );
    if !report.success() {
        anyhow::bail!("required installation work failed or remains incomplete");
    }
    if app.dry_run {
        println!("dry run complete; nothing changed");
    } else {
        println!(
            "TTY setup complete; reboot/login runs session setup automatically ({} staged jobs)",
            report.staged_session
        );
    }
    Ok(())
}

/// Render one screen into an in-memory terminal and print it as plain text.
///
/// For checking what the TUI draws without opening a window on somebody's
/// desktop and screenshotting it: this is the same `ui::draw` the real terminal
/// gets, drawn into ratatui's TestBackend instead. Run it with `env HOME=<an
/// empty dir>` to see the plan a fresh machine would get.
fn snapshot(app: &mut App, screen: &str) -> Result<()> {
    use ratatui::backend::TestBackend;

    if screen == "plan" {
        app.rebuild_plan();
    }
    if screen == "questions" {
        app.resolve_questions();
    }
    app.screen = match screen {
        "groups" => Screen::Groups,
        "questions" => Screen::Questions,
        "wallpaper" => Screen::Wallpaper,
        "plan" => Screen::Plan,
        _ => Screen::Welcome,
    };
    if screen == "wallpaper" {
        app.cursor = app.wallpaper;
    }
    // Past the tagline's typing animation, so the snapshot shows the settled frame.
    app.frame = 80;

    let mut terminal = Terminal::new(TestBackend::new(120, 44))?;
    terminal.draw(|f| ui::draw(f, app))?;
    let buffer = terminal.backend().buffer().clone();
    for y in 0..buffer.area.height {
        let line: String = (0..buffer.area.width)
            .map(|x| buffer[(x, y)].symbol().to_string())
            .collect();
        println!("{}", line.trim_end());
    }
    Ok(())
}

fn list_wallpapers(repo: &std::path::Path) -> Vec<String> {
    let mut names: Vec<String> = std::fs::read_dir(repo.join("wallpapers"))
        .map(|dir| {
            dir.flatten()
                .map(|e| e.file_name().to_string_lossy().to_string())
                .filter(|n| {
                    let n = n.to_lowercase();
                    [".png", ".jpg", ".jpeg", ".webp"]
                        .iter()
                        .any(|ext| n.ends_with(ext))
                })
                .collect()
        })
        .unwrap_or_default();
    names.sort();
    names
}

fn latest_backup() -> Option<PathBuf> {
    let root = data::expand("~/.local/state/blackwall/backups");
    let mut dirs: Vec<PathBuf> = std::fs::read_dir(root)
        .ok()?
        .flatten()
        .map(|e| e.path())
        .filter(|p| p.is_dir())
        .collect();
    dirs.sort();
    dirs.pop()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn app() -> App {
        let catalogue = Catalogue {
            packages: Default::default(),
            links: Default::default(),
            steps: Default::default(),
            questions: data::Questions {
                meta: Default::default(),
                questions: vec![data::Question {
                    id: "text".into(),
                    env: "TEST_TEXT".into(),
                    ..Default::default()
                }],
            },
            root: std::env::temp_dir(),
        };
        let system = System {
            is_arch: true,
            distro: "test".into(),
            aur_helper: None,
            has_network: false,
            in_session: false,
            hyprland: None,
            home: std::env::temp_dir(),
            user: "test".into(),
            shell: "/bin/sh".into(),
            sudo_ready: false,
        };
        let mut app = App::new(std::env::temp_dir(), catalogue, system, true, vec![]);
        app.screen = Screen::Questions;
        app
    }

    #[test]
    fn text_rows_accept_j_k_and_enter_advances() {
        let mut app = app();
        app.key(KeyCode::Char('j'));
        app.key(KeyCode::Char('k'));
        assert_eq!(app.typed.get(&0).map(String::as_str), Some("jk"));
        app.key(KeyCode::Enter);
        assert!(app.screen == Screen::Wallpaper);
    }

    #[test]
    fn escape_leaves_text_question_and_running_q_does_not_detach_worker() {
        let mut app = app();
        app.key(KeyCode::Esc);
        assert!(app.screen == Screen::Groups);
        app.screen = Screen::Running;
        app.key(KeyCode::Char('q'));
        assert!(!app.quit);
    }
}
