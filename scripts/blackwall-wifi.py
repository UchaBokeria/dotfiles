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
        })
    out.sort(key=lambda n: (not n["active"], -n["signal"]))
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
