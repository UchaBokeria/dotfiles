//! Turning what the machine has into what it still needs.
//!
//! The plan is built once, shown in full, and only then run. Nothing happens
//! before the user has seen the whole list - which is also why every item
//! carries the reason it is there.

use std::path::Path;

use crate::data::{Catalogue, Link, Package, Setting, Step};
use crate::probe::{self, LinkState, System};

#[derive(Debug, Clone)]
pub enum Action {
    /// One pacman (or AUR helper) invocation for a whole group.
    Packages {
        group: String,
        packages: Vec<Package>,
        aur: bool,
    },
    Link(Link),
    Setting(Setting),
    Step(Step),
}

#[derive(Debug, Clone, PartialEq)]
pub enum State {
    /// Will be done.
    Todo,
    /// Already true on this machine; shown greyed out, not run.
    Satisfied,
    /// Cannot be done now (no session yet, no AUR helper); deferred to phase 2.
    Deferred(String),
    /// Something is in the way and the user has to decide.
    Conflict(String),
    Running,
    Done,
    Failed(String),
    Skipped,
}

#[derive(Debug, Clone)]
pub struct Item {
    pub title: String,
    pub detail: String,
    pub action: Action,
    pub state: State,
    /// Root work is grouped so the password is asked for once.
    pub root: bool,
}

impl Item {
    pub fn is_todo(&self) -> bool {
        matches!(self.state, State::Todo | State::Conflict(_))
    }
}

pub struct Selections {
    /// Optional group names the user ticked.
    pub groups: Vec<String>,
    /// Install personal / machine-specific items too.
    pub personal: bool,
    /// File name inside `wallpapers/` to derive the first palette from.
    pub wallpaper: Option<String>,
}

pub fn build(cat: &Catalogue, sel: &Selections, sys: &System, repo: &Path) -> Vec<Item> {
    let mut items = Vec::new();

    // ---- what has to happen before any package is fetched -----------------
    for step in cat.steps.steps.iter().filter(|s| s.first) {
        items.push(step_item(step, sys, repo));
    }

    // ---- packages --------------------------------------------------------
    for group in &cat.packages.groups {
        let wanted = group.required || sel.groups.iter().any(|g| g == &group.name);
        if !wanted || group.packages.is_empty() {
            continue;
        }
        let missing = probe::missing(&group.packages);
        let (aur, repo_pkgs): (Vec<_>, Vec<_>) = missing.into_iter().partition(|p| p.is_aur());

        if !repo_pkgs.is_empty() {
            items.push(Item {
                title: format!("install {} ({} packages)", group.name, repo_pkgs.len()),
                detail: names(&repo_pkgs),
                action: Action::Packages {
                    group: group.name.clone(),
                    packages: repo_pkgs,
                    aur: false,
                },
                state: State::Todo,
                root: true,
            });
        }
        if !aur.is_empty() {
            let state = match &sys.aur_helper {
                Some(_) => State::Todo,
                None => State::Deferred("no AUR helper yet".into()),
            };
            items.push(Item {
                title: format!("install {} from the AUR ({})", group.name, aur.len()),
                detail: names(&aur),
                action: Action::Packages {
                    group: group.name.clone(),
                    packages: aur,
                    aur: true,
                },
                state,
                root: false, // the helper asks for root itself, per package
            });
        }
        if group.packages.iter().all(|p| probe::pkg_installed(&p.name)) {
            items.push(Item {
                title: format!("{} packages", group.name),
                detail: format!("{} already installed", group.packages.len()),
                action: Action::Packages {
                    group: group.name.clone(),
                    packages: vec![],
                    aur: false,
                },
                state: State::Satisfied,
                root: false,
            });
        }
    }

    // ---- files -----------------------------------------------------------
    for link in &cat.links.links {
        if link.personal && !sel.personal {
            items.push(Item {
                title: format!("skip {}", link.target),
                detail: "personal to the original machine".into(),
                action: Action::Link(link.clone()),
                state: State::Skipped,
                root: false,
            });
            continue;
        }
        if link.kind == "broken" {
            // A dangling symlink on the source machine. Recorded so it is not
            // recreated by accident.
            continue;
        }
        if link.kind == "generated" {
            // Written by the theme pipeline; linking it would point the
            // generator at its own output.
            continue;
        }
        let state = match probe::link_state(link, repo) {
            LinkState::Correct => State::Satisfied,
            LinkState::Missing => State::Todo,
            LinkState::NoSource => State::Skipped,
            LinkState::Conflict(path) => {
                State::Conflict(format!("{} exists and is not ours", path.display()))
            }
        };
        // Say what will actually happen to the file: a copy is the machine's to
        // edit afterwards, a link stays owned by the repo.
        let verb = if link.kind == "copy" { "copy" } else { "link" };
        items.push(Item {
            title: format!("{verb} {}", link.target),
            detail: if link.note.is_empty() {
                format!("from {}", link.repo)
            } else {
                link.note.clone()
            },
            action: Action::Link(link.clone()),
            state,
            root: link.target.starts_with("/usr") || link.target.starts_with("/etc"),
        });
    }

    // ---- settings --------------------------------------------------------
    for setting in &cat.links.settings {
        if setting.personal && !sel.personal {
            continue;
        }
        if probe::setting_satisfied(setting, repo) {
            continue;
        }
        items.push(Item {
            title: format!("set {} {}", setting.tool, setting.key),
            detail: if setting.note.is_empty() {
                setting.value.clone()
            } else {
                format!("{} — {}", setting.value, setting.note)
            },
            action: Action::Setting(setting.clone()),
            state: State::Todo,
            root: setting.tool == "systemctl-system",
        });
    }

    // ---- the wallpaper ---------------------------------------------------
    // Written before the theme pipeline runs: wallust derives the whole
    // palette from this one image, so it is a real choice, not a detail.
    if let Some(name) = &sel.wallpaper {
        let path = format!("$HOME/.config/wallpapers/{name}");
        let quoted = probe::shell_quote(&path).replace("$HOME", "'\"$HOME\"'");
        let check = format!(
            "grep -qxF \"$HOME/.config/wallpapers/{name}\" \"$HOME/.cache/last_wallpaper\""
        );
        let state = if probe::check_passes(&check, repo) {
            State::Satisfied
        } else {
            State::Todo
        };
        items.push(Item {
            title: format!("wallpaper: {name}"),
            detail: "the palette for the whole rice comes from this image".into(),
            action: Action::Step(Step {
                id: "wallpaper-choice".into(),
                title: format!("use {name} as the first wallpaper"),
                run: vec![format!(
                    "mkdir -p \"$HOME/.cache\" && printf '%s\\n' {quoted} > \"$HOME/.cache/last_wallpaper\""
                )],
                check,
                root: false,
                needs_session: false,
                optional: false,
                first: false,
                after: vec![],
                note: String::new(),
                group: String::new(),
            }),
            state,
            root: false,
        });
    }

    // ---- build and setup steps -------------------------------------------
    for step in &cat.steps.steps {
        if step.first {
            continue; // already at the top of the plan
        }
        if !step.group.is_empty()
            && !sel.groups.iter().any(|g| g == &step.group)
        {
            continue;
        }
        items.push(step_item(step, sys, repo));
    }

    items
}

fn step_item(step: &Step, sys: &System, repo: &Path) -> Item {
    let state = if probe::check_passes(&step.check, repo) {
        State::Satisfied
    } else if step.needs_session && !sys.in_session {
        State::Deferred("needs a running Hyprland session".into())
    } else {
        State::Todo
    };
    Item {
        title: step.title.clone(),
        detail: if step.note.is_empty() {
            step.run.first().cloned().unwrap_or_default()
        } else {
            step.note.clone()
        },
        action: Action::Step(step.clone()),
        state,
        root: step.root,
    }
}

fn names(packages: &[Package]) -> String {
    let shown: Vec<&str> = packages.iter().take(8).map(|p| p.name.as_str()).collect();
    if packages.len() > shown.len() {
        format!("{} … +{}", shown.join(" "), packages.len() - shown.len())
    } else {
        shown.join(" ")
    }
}

/// A one-line summary for the review screen.
pub fn summary(items: &[Item]) -> String {
    let todo = items.iter().filter(|i| i.is_todo()).count();
    let satisfied = items.iter().filter(|i| i.state == State::Satisfied).count();
    let deferred = items
        .iter()
        .filter(|i| matches!(i.state, State::Deferred(_)))
        .count();
    let skipped = items.iter().filter(|i| i.state == State::Skipped).count();
    format!(
        "{todo} to do · {satisfied} already done · {deferred} after first login · {skipped} skipped"
    )
}
