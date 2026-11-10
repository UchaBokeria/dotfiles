#!/usr/bin/env sh
# opencode idle-nudge watcher.
#
# Watches the latest opencode session per directory: when a turn that was
# running finishes while its pane is not focused, nudges via a tmux message
# + terminal bell. State lives in $CACHE (sessionID -> last seen status).
#
# Run from a systemd user timer or a detached tmux job, NOT from
# status-interval: it keeps state across invocations and only fires on
# running -> idle transitions.
#
# Usage: opencode-nudge.sh [directory]  (default: pane_current_path)
set -u

DIR="${1:-$(tmux display-message -p '#{pane_current_path}' 2>/dev/null || echo "")}"
[ -z "$DIR" ] && exit 0

unit="$HOME/.config/systemd/user/opencode-mobile.service"
RC_USER="$(grep OPENCODE_SERVER_USERNAME "$unit" 2>/dev/null | sed 's/.*USERNAME=//')"
RC_PASS="$(grep OPENCODE_SERVER_PASSWORD "$unit" 2>/dev/null | sed 's/.*PASSWORD=//')"
[ -z "$RC_USER" ] && exit 0
BASE="http://127.0.0.1:4096"

CACHE="${TMPDIR:-/tmp}/tmux-opencode-status-$USER"
mkdir -p "$CACHE" 2>/dev/null
STATE="$CACHE/nudge.json"

NOW_SID="$(curl -sm2 -u "$RC_USER:$RC_PASS" "$BASE/session?directory=$DIR" 2>/dev/null \
  | python3 -c "
import json,sys
try:
    ss=json.load(sys.stdin)
except Exception:
    raise SystemExit
if not ss: raise SystemExit
s=max(ss,key=lambda s:s['time']['updated'])
print(s['id'],s['time']['updated'],(s.get('title') or '')[:40])
" 2>/dev/null || echo "")"
[ -z "$NOW_SID" ] && exit 0
set -- $NOW_SID
SID="$1"; UPDATED="$2"; shift 2; TITLE="$*"

# running? one /message fetch, newest-first scan for a running tool part.
RUNNING="$(SID="$SID" RC_U="$RC_USER" RC_PW="$RC_PASS" python3 -c "
import json,os,base64,urllib.request
try:
    cred=base64.b64encode((os.environ['RC_U']+':'+os.environ['RC_PW']).encode()).decode()
    req=urllib.request.Request('http://127.0.0.1:4096/session/'+os.environ['SID']+'/message',
        headers={'Authorization':'Basic '+cred})
    msgs=json.load(urllib.request.urlopen(req,timeout=3))
    if not isinstance(msgs,list) or not msgs: print('idle'); raise SystemExit
    last=msgs[-1]
    for p in last.get('parts',[]):
        if p.get('type')=='tool' and (p.get('state') or {}).get('status')=='running':
            print('running'); raise SystemExit
    print('idle')
except SystemExit:
    raise
except Exception:
    print('unknown')
" 2>/dev/null || echo unknown)"

PREV="$(python3 -c "
import json,os
try: d=json.load(open('$STATE'))
except Exception: d={}
print(d.get('$SID',''))
" 2>/dev/null || echo "")"

# persist current
python3 -c "
import json,os
p='$STATE'
try: d=json.load(open(p))
except Exception: d={}
d['$SID']='$RUNNING:$UPDATED'
json.dump(d,open(p,'w'))
" 2>/dev/null

# fire only on running -> idle, and only if the opencode pane isn't focused
if [ "$PREV" != "" ] && [ "$RUNNING" = "idle" ]; then
  case "$PREV" in
    running:*)
      FOCUSED="$(tmux display-message -p '#{pane_current_command}' 2>/dev/null || echo "")"
      case "$FOCUSED" in
        opencode|*/opencode)
          # user is looking at it; no nudge needed
          exit 0 ;;
      esac
      tmux display-message "opencode done: $TITLE" 2>/dev/null
      printf '\a'
      ;;
  esac
fi
