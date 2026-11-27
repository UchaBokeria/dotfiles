//! Exercise the real CLI in an isolated HOME with fake external probes.
use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::PathBuf;
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

struct Fixture(PathBuf);
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

#[test]
fn previews_never_invoke_sudo_or_catalogue_shell_actions() {
    let stamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let fixture = Fixture(
        std::env::temp_dir().join(format!("blackwall-preview-{}-{stamp}", std::process::id())),
    );
    let root = &fixture.0;
    let bin = root.join("bin");
    let home = root.join("home");
    let data = root.join("installer/data");
    for directory in [&bin, &home, &data] {
        fs::create_dir_all(directory).unwrap();
    }
    for name in ["packages", "links"] {
        fs::write(data.join(format!("{name}.toml")), "").unwrap();
    }
    fs::write(
        data.join("steps.toml"),
        r#"
[[step]]
id = "fixture"
title = "fixture"
check = 'printf check >> "$SIDE_EFFECT_LOG"; exit 0'
run = ['printf run >> "$SIDE_EFFECT_LOG"']

[[step]]
id = "sddm-autologin"
title = "server autologin"
check = 'printf check >> "$SIDE_EFFECT_LOG"; exit 0'
run = ['printf run >> "$SIDE_EFFECT_LOG"']
profiles = ["server"]

[[step]]
id = "service-bluetooth"
title = "desktop bluetooth"
check = 'printf check >> "$SIDE_EFFECT_LOG"; exit 0'
run = ['printf run >> "$SIDE_EFFECT_LOG"']
optional = true
profiles = ["desktop"]
"#,
    )
    .unwrap();
    fs::write(
        data.join("questions.toml"),
        r#"
[[question]]
id = "fixture"
title = "fixture"
env = "BLACKWALL_PREVIEW_FIXTURE"
detect = 'printf detect >> "$SIDE_EFFECT_LOG"; printf detected'
"#,
    )
    .unwrap();
    for (name, body) in [
        ("sudo", "printf sudo >> \"$SIDE_EFFECT_LOG\"; exit 0"),
        ("ping", "exit 1"),
        ("hyprctl", "exit 1"),
        ("getent", "exit 1"),
        ("pacman", "exit 1"),
    ] {
        let path = bin.join(name);
        fs::write(&path, format!("#!/bin/sh\n{body}\n")).unwrap();
        fs::set_permissions(path, fs::Permissions::from_mode(0o755)).unwrap();
    }
    let log = root.join("side-effects");
    for args in [
        vec!["--dry-run", "--apply"],
        vec!["--snapshot", "plan"],
        vec!["--snapshot", "questions"],
    ] {
        let output = Command::new(env!("CARGO_BIN_EXE_blackwall-install"))
            .args(&args)
            .current_dir(root)
            .env("BLACKWALL_ROOT", root)
            .env("HOME", &home)
            .env("USER", "fixture")
            .env("PATH", format!("{}:/usr/bin:/bin", bin.display()))
            .env("SIDE_EFFECT_LOG", &log)
            .env_remove("BLACKWALL_PREVIEW_FIXTURE")
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{args:?}: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        assert!(
            !log.exists(),
            "{args:?} ran a mutating probe: {}",
            fs::read_to_string(&log).unwrap_or_default()
        );
        assert_eq!(
            fs::read_dir(&home).unwrap().count(),
            0,
            "{args:?} changed HOME"
        );
    }

    // The server profile plan carries the autologin step and drops the
    // desktop-only bluetooth step; the desktop plan is the reverse. Headless
    // previews print each step's title, and none of them may touch HOME or run
    // a probe. `--profile server --dry-run` alone is itself headless (no TUI).
    for (profile, flags, present, absent) in [
        (
            "server",
            vec!["--dry-run", "--apply"],
            "server autologin",
            "desktop bluetooth",
        ),
        (
            "server",
            vec!["--dry-run"],
            "server autologin",
            "desktop bluetooth",
        ),
        (
            "desktop",
            vec!["--dry-run", "--apply"],
            "desktop bluetooth",
            "server autologin",
        ),
    ] {
        let output = Command::new(env!("CARGO_BIN_EXE_blackwall-install"))
            .args(["--profile", profile])
            .args(&flags)
            .current_dir(root)
            .env("BLACKWALL_ROOT", root)
            .env("HOME", &home)
            .env("USER", "fixture")
            .env("PATH", format!("{}:/usr/bin:/bin", bin.display()))
            .env("SIDE_EFFECT_LOG", &log)
            .env_remove("BLACKWALL_PREVIEW_FIXTURE")
            .env_remove("BLACKWALL_PROFILE")
            .output()
            .unwrap();
        let stdout = String::from_utf8_lossy(&output.stdout);
        assert!(
            output.status.success(),
            "profile {profile} {flags:?}: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        assert!(
            stdout.contains(present),
            "profile {profile} {flags:?} plan should contain {present:?}: {stdout}"
        );
        assert!(
            !stdout.contains(absent),
            "profile {profile} {flags:?} plan should exclude {absent:?}"
        );
        assert!(!log.exists(), "profile {profile} {flags:?} ran a probe");
        assert_eq!(fs::read_dir(&home).unwrap().count(), 0, "changed HOME");
    }

    // --answers: a missing file is a clear error, never a silent default.
    let output = Command::new(env!("CARGO_BIN_EXE_blackwall-install"))
        .args([
            "--dry-run",
            "--apply",
            "--answers",
            "/nonexistent/answers.toml",
        ])
        .current_dir(root)
        .env("BLACKWALL_ROOT", root)
        .env("HOME", &home)
        .env("PATH", format!("{}:/usr/bin:/bin", bin.display()))
        .output()
        .unwrap();
    assert!(!output.status.success());
    assert!(String::from_utf8_lossy(&output.stderr).contains("answers file"));
    // An unknown profile is rejected too.
    let output = Command::new(env!("CARGO_BIN_EXE_blackwall-install"))
        .args(["--profile", "laptop", "--dry-run", "--apply"])
        .current_dir(root)
        .env("BLACKWALL_ROOT", root)
        .env("HOME", &home)
        .env("PATH", format!("{}:/usr/bin:/bin", bin.display()))
        .output()
        .unwrap();
    assert!(!output.status.success());
    for (index, modifier) in ["--dry-run", "--snapshot"].into_iter().enumerate() {
        let backup = root.join(format!("restore-fixture-{index}"));
        fs::create_dir(&backup).unwrap();
        let original = backup.join("restored-value");
        fs::write(&original, "must stay in backup").unwrap();
        let output = Command::new(env!("CARGO_BIN_EXE_blackwall-install"))
            .args(["--restore", backup.to_str().unwrap(), modifier])
            .current_dir(root)
            .env("BLACKWALL_ROOT", root)
            .env("HOME", &home)
            .env("PATH", format!("{}:/usr/bin:/bin", bin.display()))
            .env("SIDE_EFFECT_LOG", &log)
            .output()
            .unwrap();
        assert!(
            !output.status.success(),
            "restore combined with {modifier} must be rejected"
        );
        assert!(String::from_utf8_lossy(&output.stderr).contains("cannot combine"));
        assert_eq!(
            fs::read_to_string(&original).unwrap(),
            "must stay in backup"
        );
        assert_eq!(
            fs::read_dir(&home).unwrap().count(),
            0,
            "{modifier} restored into HOME"
        );
        assert!(!log.exists());
    }
}
