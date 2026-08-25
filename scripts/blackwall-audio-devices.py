"""List pipewire audio devices of one direction, as JSON.

Read from pw-dump rather than pactl: pactl's source list only covers
ALSA-backed devices and the auto-generated monitors, so a loopback source -
which is the *only* input this machine has - is invisible to it.

Hidden here: `.monitor` nodes (pulse's automatic loopback of every sink, which
would offer "record my own speakers" as an input device) and `input.*` nodes
(the sink half of a loopback pair, which is plumbing, not somewhere you would
choose to send audio).
"""
import json
import sys

WANT = "Audio/Sink" if sys.argv[1] == "sink" else "Audio/Source"
DEFAULT = sys.argv[2] if len(sys.argv) > 2 else ""

out = []
for obj in json.load(sys.stdin):
    if obj.get("type") != "PipeWire:Interface:Node":
        continue
    props = (obj.get("info") or {}).get("props") or {}
    if not (props.get("media.class") or "").startswith(WANT):
        continue
    name = props.get("node.name") or ""
    if name.endswith(".monitor") or name.startswith("input."):
        continue
    out.append({
        "id": obj["id"],
        "name": name,
        "desc": props.get("node.description") or name,
        "active": name == DEFAULT,
        # A loopback source hears whatever is playing, not the room. Saying so
        # is the difference between a working mic slider and a confusing one.
        "loopback": bool(props.get("node.link-group")),
    })

out.sort(key=lambda d: (not d["active"], d["desc"].lower()))
print(json.dumps(out))
