"""Parse `nmcli device wifi list` into something a panel can render.

nmcli's terse output separates fields with colons - and a BSSID is six
colon-separated octets, so a naive split shreds it. With escaping left on
(the default) nmcli writes those as `\\:`, which is what the regex below
splits around.
"""
import re
import subprocess
import sys
import json

FIELDS = "IN-USE,SSID,SIGNAL,SECURITY,BSSID,FREQ,CHAN"
SPLIT = re.compile(r"(?<!\\):")


def unescape(v: str) -> str:
    return v.replace("\\:", ":").replace("\\\\", "\\")


def saved_profiles() -> set[str]:
    r = subprocess.run(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
                       capture_output=True, text=True)
    out = set()
    for line in r.stdout.splitlines():
        parts = SPLIT.split(line)
        if len(parts) >= 2 and "wireless" in parts[-1]:
            out.add(unescape(parts[0]))
    return out


def security_label(raw: str) -> tuple[str, str]:
    """A human word plus the detail. 'WPA1 WPA2' is a mixed-mode access point,
    which matters: it means the network still accepts the older handshake."""
    s = raw.strip()
    if not s or s == "--":
        return "open", "no encryption"
    if "WPA3" in s:
        return ("wpa2/3" if "WPA2" in s else "wpa3"), s.lower()
    if "WPA2" in s and "WPA1" in s:
        return "wpa1/2", "mixed mode - accepts the older handshake"
    if "WPA2" in s:
        return "wpa2", s.lower()
    if "WPA1" in s:
        return "wpa1", "deprecated"
    if "WEP" in s:
        return "wep", "broken - avoid"
    return s.lower()[:8], s.lower()


# The wifi-strength ladder, verified by rendering the range out of
# SymbolsNerdFont-Regular.ttf and looking at it: f091f is a hollow arc, f0922
# about half filled, f0925 most of the way, f0928 solid. Each level has a
# padlock variant three codepoints along, so security rides in the same glyph
# rather than needing a second one beside it.
WIFI_BARS = [0xF091F, 0xF0922, 0xF0925, 0xF0928]
LOCK_OFFSET = 2


def wifi_glyph(signal: int, secure: bool) -> str:
    """Signal strength as one character, padlocked if the network is closed."""
    level = 0 if signal < 30 else 1 if signal < 55 else 2 if signal < 75 else 3
    cp = WIFI_BARS[level] + (LOCK_OFFSET if secure else 0)
    return chr(cp)


def main() -> int:
    r = subprocess.run(
        ["nmcli", "-t", "-f", FIELDS, "device", "wifi", "list"],
        capture_output=True, text=True)
    saved = saved_profiles()
    seen, out = set(), []
    for line in r.stdout.splitlines():
        parts = [unescape(p) for p in SPLIT.split(line)]
        if len(parts) < 7:
            continue
        inuse, ssid, signal, security, bssid, freq, chan = parts[:7]
        if not ssid or ssid in seen:
            continue
        seen.add(ssid)
        label, detail = security_label(security)
        mhz = int(re.sub(r"\D", "", freq) or 0)
        out.append({
            "ssid": ssid,
            "active": inuse.strip() == "*",
            "signal": int(signal) if signal.isdigit() else 0,
            "secure": label != "open",
            "sec": label,
            "sec_detail": detail,
            "bssid": bssid,
            # The last two octets are enough to tell two radios of the same
            # access point apart, which is the only reason to show a MAC here.
            "mac_tail": ":".join(bssid.split(":")[-2:]) if bssid else "",
            "band": "5G" if mhz >= 5000 else ("6G" if mhz >= 5900 else "2.4G"),
            "chan": chan,
            "saved": ssid in saved,
            "glyph": wifi_glyph(int(signal) if signal.isdigit() else 0,
                                label != "open"),
        })
    out.sort(key=lambda n: (not n["active"], -n["signal"]))
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
