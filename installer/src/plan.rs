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
    pub required: bool,
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
    pub answers: Vec<(String, String)>,
    pub dry_run: bool,
    /// Which machine shape this install targets. Desktop is the default and
    /// behaves exactly as before; server is the headless KVM shape.
    pub profile: Profile,
}

/// Which machine shape the install targets.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum Profile {
    #[default]
    Desktop,
    Server,
}

impl Profile {
    pub fn name(&self) -> &'static str {
        match self {
            Profile::Desktop => "desktop",
            Profile::Server => "server",
        }
    }

    pub fn parse(s: &str) -> Result<Self, String> {
        match s {
            "desktop" => Ok(Profile::Desktop),
            "server" => Ok(Profile::Server),
            other => Err(format!(
                "unknown profile {other:?}; expected \"desktop\" or \"server\""
            )),
        }
    }
}

/// Optional groups the server profile installs on top of the required ones
/// (core, fonts, theming - required groups always install on both profiles).
///
/// The merged server IS the owner's daily desktop over VNC (DECISIONS.md /
/// DESIGN.md): Chrome, Brave, WhatsApp, editors, media, office, AI agent CLIs
/// all run on it. So server = everything desktop selects, MINUS only:
///
///   gaming, virt, dev-unity   left behind by the owner (Lutris/Steam,
///                             libvirt + win11 VM, Unity Hub)
///   hardware                  bluetooth, monitor brightness (i2c),
///                             NetworkManager/wifi, GPU vendor drivers, laptop
///                             power, printing (cups lives in `system`, which
///                             also carries kernel/boot tooling the server
///                             still needs, so `system` stays SELECTED and only
///                             the hardware *steps* are desktop-only)
///
/// Bluez/blueman live in required `core` and stay installed, but the server
/// profile never enables bluetooth (service-bluetooth is desktop-only).
pub fn server_groups() -> &'static [&'static str] {
    &[
        "hypr-extras",
        "shell-tools",
        "editors",
        "dev",
        "dev-ada",
        "browsers",
        "media",
        "messaging",
        "network",
        "security",
        "office",
        "system",
        "ai",
        "misc",
        "kde-plasma",
        "kde-apps",
    ]
}

fn profile_allows(step_profiles: &[String], profile: Profile) -> bool {
    step_profiles.is_empty() || step_profiles.iter().any(|p| p == profile.name())
}

pub fn build(cat: &Catalogue, sel: &Selections, sys: &System, repo: &Path) -> Vec<Item> {
    let mut items = Vec::new();

    // ---- what has to happen before any package is fetched -----------------
    let mut dropped: Vec<String> = Vec::new();
    for step in cat.steps.steps.iter().filter(|s| s.first) {
        if !profile_allows(&step.profiles, sel.profile) {
            dropped.push(step.id.clone());
            continue;
        }
        items.push(step_item(step, sys, repo, sel));
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
                required: group.required,
            });
        }
        if !aur.is_empty() {
            // "No AUR helper" is only true until the `aur-helper` step runs,
            // and that step is `first = true`, so it runs before this item.
            // Deferring anyway meant a fresh box installed yay and then
            // skipped every AUR package in the same pass - eww, wlogout,
            // wallust and wacli among them, which is most of the rice.
            let bootstrapping = cat.steps.steps.iter().any(|s| {
                s.id == "aur-helper"
                    && (sel.dry_run || !probe::check_passes_with_env(&s.check, repo, &sel.answers))
            });
            let state = match (&sys.aur_helper, bootstrapping) {
                (Some(_), _) => State::Todo,
                (None, true) => State::Todo,
                (None, false) => State::Deferred("no AUR helper yet".into()),
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
                required: group.required,
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
                required: group.required,
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
                required: false,
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
            LinkState::NoSource => State::Failed("source is missing from the checkout".into()),
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
            required: true,
        });
    }

    // ---- settings --------------------------------------------------------
    for setting in &cat.links.settings {
        if setting.personal && !sel.personal {
            continue;
        }
        if !sel.dry_run && probe::setting_satisfied(setting, repo) {
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
            required: true,
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
        let state = if !sel.dry_run && probe::check_passes(&check, repo) {
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
                interactive: false,
                optional: false,
                first: false,
                after: vec![],
                note: String::new(),
                group: String::new(),
                profiles: vec![],
            }),
            state,
            root: false,
            required: true,
        });
    }

    // ---- build and setup steps -------------------------------------------
    for step in &cat.steps.steps {
        if step.first {
            continue; // already at the top of the plan
        }
        if !step.group.is_empty() && !sel.groups.iter().any(|g| g == &step.group) {
            continue;
        }
        if !profile_allows(&step.profiles, sel.profile) {
            dropped.push(step.id.clone());
            continue;
        }
        items.push(step_item(step, sys, repo, sel));
    }

    // A step another one waits on may be filtered out by the profile (e.g.
    // service-networkmanager on the server). The runner fails a step whose
    // `after` names something that is not in the plan, so forget those edges.
    if !dropped.is_empty() {
        for item in &mut items {
            if let Action::Step(step) = &mut item.action {
                step.after.retain(|dep| !dropped.contains(dep));
            }
        }
    }

    items
}

fn step_item(step: &Step, sys: &System, repo: &Path, sel: &Selections) -> Item {
    let state = if !sel.dry_run && probe::check_passes_with_env(&step.check, repo, &sel.answers) {
        State::Satisfied
    } else if step.interactive {
        State::Deferred("manual account setup; requires an interactive terminal".into())
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
        required: !step.optional,
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
    format!("{todo} to do · {satisfied} already done · {deferred} deferred · {skipped} skipped")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dry_run_does_not_execute_catalogue_checks() {
        let catalogue = Catalogue {
            packages: Default::default(),
            links: Default::default(),
            questions: Default::default(),
            steps: crate::data::Steps {
                meta: Default::default(),
                steps: vec![Step {
                    id: "check".into(),
                    title: "check".into(),
                    run: vec!["true".into()],
                    check: "exit 0".into(),
                    root: false,
                    needs_session: false,
                    interactive: false,
                    optional: false,
                    first: false,
                    after: vec![],
                    note: String::new(),
                    group: String::new(),
                    profiles: vec![],
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
        let selection = Selections {
            groups: vec![],
            personal: false,
            wallpaper: None,
            answers: vec![],
            dry_run: true,
            profile: Profile::Desktop,
        };
        let items = build(&catalogue, &selection, &system, &std::env::temp_dir());
        assert_eq!(items[0].state, State::Todo);
        let normal = Selections {
            dry_run: false,
            ..selection
        };
        assert_eq!(
            build(&catalogue, &normal, &system, &std::env::temp_dir())[0].state,
            State::Satisfied
        );
    }
    #[test]
    fn unsatisfied_interactive_accounts_are_manual_even_in_a_live_session() {
        let mut step: Step = toml::from_str(
            r#"
            id = "account-auth"
            title = "Pair the account"
            interactive = true
            check = "false"
            run = ["exit 88"]
        "#,
        )
        .unwrap();
        let mut system = System {
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
        let selection = Selections {
            groups: vec![],
            personal: false,
            wallpaper: None,
            answers: vec![],
            dry_run: false,
            profile: Profile::Desktop,
        };
        for in_session in [false, true] {
            system.in_session = in_session;
            let item = step_item(&step, &system, &std::env::temp_dir(), &selection);
            assert!(matches!(item.state, State::Deferred(_)));
            assert!(!item.is_todo());
            let (tx, rx) = std::sync::mpsc::channel();
            crate::exec::Runner::new(std::env::temp_dir(), false).run(vec![item], tx);
            let events: Vec<_> = rx.into_iter().collect();
            assert!(!events
                .iter()
                .any(|event| matches!(event, crate::exec::Event::Start(_))));
            assert!(events.iter().any(|event| matches!(event, crate::exec::Event::AllDone(report) if !report.success() && report.required_pending == 1)));
        }
        step.check = "true".into();
        assert_eq!(
            step_item(&step, &system, &std::env::temp_dir(), &selection).state,
            State::Satisfied
        );
    }

    fn fixture_catalogue(steps: Vec<Step>, groups: Vec<crate::data::Group>) -> Catalogue {
        Catalogue {
            packages: crate::data::Packages {
                meta: Default::default(),
                groups,
            },
            links: Default::default(),
            questions: Default::default(),
            steps: crate::data::Steps {
                meta: Default::default(),
                steps,
            },
            root: std::env::temp_dir(),
        }
    }

    fn fixture_system() -> System {
        System {
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
        }
    }

    fn fixture_step(id: &str) -> Step {
        Step {
            id: id.into(),
            title: id.into(),
            run: vec!["true".into()],
            check: "exit 1".into(),
            root: false,
            needs_session: false,
            interactive: false,
            optional: true,
            first: false,
            after: vec![],
            note: String::new(),
            group: String::new(),
            profiles: vec![],
        }
    }

    fn fixture_group(name: &str, required: bool) -> crate::data::Group {
        crate::data::Group {
            name: name.into(),
            required,
            description: String::new(),
            packages: vec![crate::data::Package {
                name: format!("{name}-pkg"),
                source: "repo".into(),
                why: String::new(),
            }],
        }
    }

    fn selections(profile: Profile) -> Selections {
        Selections {
            groups: server_groups().iter().map(|g| g.to_string()).collect(),
            personal: false,
            wallpaper: None,
            answers: vec![],
            dry_run: true,
            profile,
        }
    }

    #[test]
    fn server_profile_selects_desktop_minus_hardware_and_left_behind() {
        let groups = server_groups();
        // The merged server is the owner's daily desktop over VNC: browsers,
        // messaging, editors, ai, media, office all run on it.
        for want in [
            "hypr-extras",
            "shell-tools",
            "editors",
            "dev",
            "dev-ada",
            "browsers",
            "media",
            "messaging",
            "network",
            "security",
            "office",
            "system",
            "ai",
            "misc",
            "kde-plasma",
            "kde-apps",
        ] {
            assert!(groups.contains(&want), "server must include {want}");
        }
        // Left behind by the owner (gaming incl. Lutris/Steam, virt/libvirt +
        // win11 VM, dev-unity/Unity Hub) or genuinely empty (unclassified).
        for excluded in ["gaming", "virt", "dev-unity", "unclassified"] {
            assert!(
                !groups.contains(&excluded),
                "server must not include {excluded}"
            );
        }
    }

    #[test]
    fn server_plan_has_autologin_but_no_desktop_hardware_steps() {
        let mut autologin = fixture_step("sddm-autologin");
        autologin.profiles = vec!["server".into()];
        autologin.optional = false;
        let mut bluetooth = fixture_step("service-bluetooth");
        bluetooth.profiles = vec!["desktop".into()];
        bluetooth.optional = true;
        let mut i2c = fixture_step("group-i2c");
        i2c.profiles = vec!["desktop".into()];
        i2c.optional = true;
        let common = fixture_step("wallust-palette");
        let catalogue = fixture_catalogue(vec![autologin, bluetooth, i2c, common], vec![]);
        let system = fixture_system();

        let server_ids: Vec<String> = build(
            &catalogue,
            &selections(Profile::Server),
            &system,
            &std::env::temp_dir(),
        )
        .into_iter()
        .map(|item| match &item.action {
            Action::Step(step) => step.id.clone(),
            _ => String::new(),
        })
        .collect();
        assert!(server_ids.contains(&"sddm-autologin".to_string()));
        assert!(!server_ids.contains(&"service-bluetooth".to_string()));
        assert!(!server_ids.contains(&"group-i2c".to_string()));
        assert!(server_ids.contains(&"wallust-palette".to_string()));

        let desktop = Selections {
            groups: vec![],
            dry_run: true,
            ..selections(Profile::Desktop)
        };
        let desktop_ids: Vec<String> = build(&catalogue, &desktop, &system, &std::env::temp_dir())
            .into_iter()
            .map(|item| match &item.action {
                Action::Step(step) => step.id.clone(),
                _ => String::new(),
            })
            .collect();
        assert!(!desktop_ids.contains(&"sddm-autologin".to_string()));
        assert!(desktop_ids.contains(&"service-bluetooth".to_string()));
        assert!(desktop_ids.contains(&"group-i2c".to_string()));
        assert!(desktop_ids.contains(&"wallust-palette".to_string()));
    }

    #[test]
    fn server_dry_run_excludes_hardware_groups() {
        // The plan builder only installs required groups plus ticked ones, so
        // feed the server set: hardware/desktop-extra groups must contribute
        // no package items. `missing` would shell out to pacman, so give the
        // excluded groups no packages and the wanted groups one fake package
        // each (missing() on an unknown name = missing = Todo item).
        let mut groups = vec![
            fixture_group("core", true),
            fixture_group("fonts", true),
            fixture_group("theming", true),
        ];
        for name in [
            "hypr-extras",
            "shell-tools",
            "editors",
            "dev",
            "dev-ada",
            "browsers",
            "media",
            "messaging",
            "network",
            "security",
            "office",
            "system",
            "ai",
            "misc",
            "kde-plasma",
            "kde-apps",
        ] {
            groups.push(fixture_group(name, false));
        }
        for name in ["gaming", "virt", "dev-unity", "unclassified"] {
            groups.push(crate::data::Group {
                name: name.into(),
                required: false,
                description: String::new(),
                packages: vec![],
            });
        }
        let catalogue = fixture_catalogue(vec![], groups);
        let items = build(
            &catalogue,
            &selections(Profile::Server),
            &fixture_system(),
            &std::env::temp_dir(),
        );
        let package_groups: Vec<String> = items
            .iter()
            .filter_map(|item| match &item.action {
                Action::Packages { group, .. } => Some(group.clone()),
                _ => None,
            })
            .collect();
        for want in [
            "core",
            "fonts",
            "theming",
            "hypr-extras",
            "shell-tools",
            "editors",
            "dev",
            "dev-ada",
            "browsers",
            "media",
            "messaging",
            "network",
            "security",
            "office",
            "system",
            "ai",
            "misc",
            "kde-plasma",
            "kde-apps",
        ] {
            assert!(
                package_groups.contains(&want.to_string()),
                "server plan must install {want}"
            );
        }
        for excluded in ["gaming", "virt", "dev-unity", "unclassified"] {
            assert!(
                !package_groups.contains(&excluded.to_string()),
                "server plan must not install {excluded}"
            );
        }
    }

    fn step_ids(items: &[Item]) -> Vec<String> {
        items
            .iter()
            .filter_map(|item| match &item.action {
                Action::Step(step) => Some(step.id.clone()),
                _ => None,
            })
            .collect()
    }

    #[test]
    fn filtered_step_is_forgotten_by_its_dependents() {
        let mut nm = fixture_step("service-networkmanager");
        nm.profiles = vec!["desktop".into()];
        let mut later = fixture_step("session-prepare");
        later.after = vec!["service-networkmanager".into(), "wallust-palette".into()];
        let catalogue = fixture_catalogue(vec![nm, fixture_step("wallust-palette"), later], vec![]);
        let server = build(
            &catalogue,
            &selections(Profile::Server),
            &fixture_system(),
            &std::env::temp_dir(),
        );
        let after: Vec<String> = server
            .iter()
            .find_map(|i| match &i.action {
                Action::Step(s) if s.id == "session-prepare" => Some(s.after.clone()),
                _ => None,
            })
            .unwrap();
        assert_eq!(after, vec!["wallust-palette".to_string()]);
        let desktop = build(
            &catalogue,
            &selections(Profile::Desktop),
            &fixture_system(),
            &std::env::temp_dir(),
        );
        assert!(step_ids(&desktop).contains(&"service-networkmanager".to_string()));
    }

    /// The shipped catalogue, not a fixture: the server plan has autologin,
    /// no hardware steps, and no step waits on something the plan dropped.
    #[test]
    fn shipped_catalogue_server_plan_is_closed_and_hardware_free() {
        let repo = Path::new(env!("CARGO_MANIFEST_DIR")).join("..");
        let catalogue = Catalogue::load(&repo).expect("catalogue loads");
        for group in server_groups() {
            assert!(
                catalogue.packages.groups.iter().any(|g| g.name == *group),
                "server group {group} is not in packages.toml"
            );
        }
        // Only steps are under test; dropping packages and links keeps the test
        // from spawning pacman once per package.
        let mut catalogue = catalogue;
        catalogue.packages.groups.clear();
        catalogue.links.links.clear();
        catalogue.links.settings.clear();
        let system = fixture_system();
        let server = build(&catalogue, &selections(Profile::Server), &system, &repo);
        let ids = step_ids(&server);
        assert!(ids.contains(&"sddm-autologin".to_string()));
        for hardware in ["service-bluetooth", "group-i2c", "service-networkmanager"] {
            assert!(!ids.contains(&hardware.to_string()), "{hardware} on server");
        }
        for item in &server {
            if let Action::Step(step) = &item.action {
                for dep in &step.after {
                    assert!(
                        ids.contains(dep),
                        "{} waits on {dep}, which is not planned",
                        step.id
                    );
                }
            }
        }
        let desktop = build(&catalogue, &selections(Profile::Desktop), &system, &repo);
        let ids = step_ids(&desktop);
        assert!(!ids.contains(&"sddm-autologin".to_string()));
        for hardware in ["service-bluetooth", "group-i2c", "service-networkmanager"] {
            assert!(
                ids.contains(&hardware.to_string()),
                "{hardware} missing on desktop"
            );
        }
    }

    #[test]
    fn profile_parses_only_known_names() {
        assert_eq!(Profile::parse("server"), Ok(Profile::Server));
        assert_eq!(Profile::parse("desktop"), Ok(Profile::Desktop));
        assert!(Profile::parse("laptop").is_err());
    }
}
