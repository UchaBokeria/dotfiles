---
name: readb
description: Access remote Android phones and Quest headsets through the readb server. Use for adb-style commands, screenshots, logs, installs and UI tests on linked devices, and to help link and pair a new device.
---
<!-- managed-by: readb -->

readb is the only route to the user's phones and headsets. Never use direct adb,
USB, `adb tcpip`, `adb usb` or `adb reboot`, and never change VPNs, pairing or
keys. Never touch the user's calls, messages or other apps; stay inside the task.

## Find the device

```sh
readb ls                      # ID  NAME  STATE ...
readb device inspect DEV
readb history -d DEV -n 20    # recent events of one device
```

A device ref is the ID (`dev_0123456789ab`), the name, or a unique prefix (3+
chars). With one device you can omit it. A name may start with `dev_`
(`dev_phone`) but never is `dev_` plus hex digits.

Which device: use the one the user named. If they did not and `readb ls` shows more
than one, ask which (show the list). Follow any project or user instructions about which
device is for development; never pick someone's personal phone on your own.
No device yet, or the one asked for is missing: help the user link it (below).

Only `online` is usable:

| State | Do |
|---|---|
| `online` | Go ahead |
| `needs_pairing` | Stop. Ask the user to finish pairing in the readb app (it guides them and fills the code in itself) |
| `connecting` | Wait 10-30 s, check again; still stuck: `readb device reconnect DEV` (restarts adb and says why it is not online) |
| `needs_wifi` | The user must join any Wi-Fi once (after a phone restart readb needs Wi-Fi for a moment; then mobile data works). Report it, do not try to fix it |
| `debug_off` | Ask the user to turn Wireless debugging on (their own off is respected: reconnect never overrides it) |
| `offline`, `linked` | Report it; the user checks the phone and the readb app |
| `removed` | Report it |

Devices keep working on mobile data once readb has started on them (the `helper`, see
`docs/v1/helper.md`); `Device.helper` is `running`, `starting` or `needs_wifi_once`.

Never ask the user to paste pairing codes into chat. The app fills the code in itself
("Fill in code automatically", on by default).

## Link a new device

Ask for a name (short, e.g. `work-phone`; not `dev_` plus hex) and the kind (phone or
Quest). The QR codes and link code are secrets for the user's eyes: have the user run
the command in their own terminal rather than printing it into chat or logs.

```sh
readb device link --name NAME              # phone (default); add --kind quest for a Quest
readb device link --relink NAME            # re-link a device that was reset or reinstalled
```

It prints two QR codes side by side. Walk the user through:
1. **Get the app** (left QR, or `https://HOST/app` on the phone) and install it.
2. **Link this device** (right QR): scan it in readb, or type the code shown (10 min).
3. In the app, follow the pairing step: it opens Wireless debugging; the user taps
   "Pair device with pairing code" and readb fills the code in. Pairing is once only.
4. Needs Wi-Fi for that first start (any Wi-Fi, no internet needed); afterwards mobile
   data works. Then `readb ls` shows the device `online`.

A Quest has no pairing screen: its adb key is authorized once over USB (the user does
this; see the readb docs). Removing a device (`readb device rm`) only when the user asks.

## Run things

```sh
readb run DEV -- getprop ro.product.model
readb run DEV -- sh -c 'ls /sdcard/*.png | wc -l'      # device shell syntax needs sh -c
readb screenshot DEV -o shot.png        # or -o - > shot.png
readb apk DEV app-debug.apk -r            # install an APK on the device, replace (device last also works)
readb push DEV - /sdcard/x < file          # pull: readb pull DEV REMOTE LOCAL|-
readb logcat DEV | grep -m1 FATAL
```

Arguments after `--` reach the device exactly as given.

`readb apk` puts an APK on a device. Do not use `readb install` (that installs the
readb server) or `readb app publish` (uploads the readb app to the server) for that.

After `readb app publish`, the server updates the readb app on every device running an
older build by itself (a shared session called `readb app update`; it never interrupts an
exclusive one). Do not reinstall the app by hand to roll it out; `readb history` shows
`app.updated` or `app.update_failed`.

## Sessions

Name and reason are required and shown to everyone waiting. Open one for any
multi-step work, end it when done.

```sh
export READB_SESSION=$(readb session start DEV --name 'UI test' --reason 'check panel' \
  --agent claude --project myapp --exclusive --no-wait -q)
readb tap 540 1200
readb key BACK
readb session end
```

- **shared** (default): run, shell, apk, push, pull, logcat, screenshot. Many at once.
- **exclusive**: tap, key and anything that must not be interrupted. One holder; others wait.
- Busy devices make commands wait and print `queued #N ...` on stderr. Report the
  holder; never bypass it. `--no-wait` exits 75 instead; then wait or ask.
- Always end your session (`readb session end`). Exclusive ones also expire when idle.
- `READB_AGENT` and `READB_PROJECT` label one-off sessions.

## Scripts and pipes

stdout is data, stderr is messages. `-q` ids, `--json` one document, `--format`.
`readb run` and `shell` return the device command's exit status; 64 usage,
69 server unreachable, 75 busy, 77 not allowed, 141 closed pipe.
`readb run` forwards stdin that is a file or a pipe with data (a silent pipe is skipped after 0.5 s; `--stdin` waits): use `--no-stdin` (or `< /dev/null`) inside `while read` loops.
`readb ls -q | xargs -n1 readb device inspect`.

## Rules

- Awake is not unlocked. Do not touch PINs or private data.
- A Quest is held awake and unlocked by the server while it is online (keep-alive, on by default;
  `readb device inspect quest` shows `keep alive`), so screenshots and UI tests see a live screen even
  with nobody wearing it. Never send `prox_close` or `automation_disable` yourself. A PIN lock is not
  removed: if one is up, history shows `headset.locked`; report it. Keep-alive costs the headset's
  battery: if it is on battery and low it lets go by itself (`headset.keepalive_paused`).
- Dropped connection is not proof a command stopped: inspect before retrying.
  After an adb repair, `run`, `shell`, `apk`, `push`, `tap` and `key` are not repeated
  for you: `503 adb_repaired` means check, then run it again once.
- Never expose tokens, link codes or pairing codes. Link or remove devices only when
  the user asks.
- Server problems: `readb doctor`, `readb status`, `readb logs -n 50`.
- Details: `readb --help`, `readb COMMAND --help`.
