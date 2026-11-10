#!/usr/bin/env sh
# tmux status segment: opencode context.
#
# Renders only when the active pane runs opencode, empty otherwise.
# Each segment is a raised pill with rounded caps — the same capsule
# language as the pill status variant — with colored text per segment:
#   rc      pinned for mobile (📲 session title) — green lit / faint ○
#   ext     active browser.json entry vs bridge :9225 (puzzle = extension)
#   model   session model + variant (short label, never wraps: tmux truncates)
#   ctx     cumulative session tokens (spend proxy, NOT live context %)
#   $       session cost + wall time
#   tool    last tool used in the session (cached per session+updated)
#   bg      child sessions with recent activity
#   goal    active goal-plugin objective, truncated
#   mcp     configured MCP server count
#   git      branch + dirty/ahead (starship  + ± N)
#   vim     vim plugin enabled in tui.json (static; live mode stays in TUI)
#
# Progressive collapse by pane width (mirrors Claude fit + footerWidthPolicy):
#   full (>=170): all
#   wide (>=140): drop vim, mcp
#   mid  (>=110): rc · ext · ctx · git
#   low  (>=80):  rc · ext · git
#   tiny (<80):   git only
#
# No rate-limit segment: the serve API exposes no quota endpoint and there
# is no local quota state file. No live ctx% either: session tokens are
# cumulative, while the live window % only exists inside the TUI process.
set -u

pane_path="${1:-}"
width="${2:-0}"
pane_cmd="${3:-}"

# Not an opencode pane: render nothing. The command arrives as an explicit
# arg because TMUX_PANE is not guaranteed inside a tmux #() subshell.
if [ -z "$pane_cmd" ]; then
  pane_cmd="$(tmux display-message -p '#{pane_current_command}' 2>/dev/null || echo "")"
fi
case "$pane_cmd" in
  opencode|*/opencode) ;;
  *) printf '' && exit 0 ;;
esac

if [ -z "$pane_path" ]; then
  pane_path="$(tmux display-message -p '#{pane_current_path}' 2>/dev/null || echo "")"
fi

# ── pill wrapper: raised capsule with rounded caps ──────────────────────
# Same joinery as segment.conf:  (U+E0B6) in fg=raised on the bar bg,
# then the body on bg=raised starting immediately, then  (U+E0B4) in
# fg=raised on the bar bg. Adjacent, no gaps.
pill() {
  # $1 = body text; $2 = fg color for the text (e.g. "@bw_good").
  printf '#[fg=#{@bw_raised},bg=default]#[fg=%s,bg=#{@bw_raised}] %s #[fg=#{@bw_raised},bg=default,nobold]' "$2" "$1"
}

RC_ICON='󰄜'
EXT_ICON=''
GIT_ICON=''
VIM_ICON=''
CTX_ICON=''
COST_ICON=''
TOOL_ICON=''
BG_ICON=''
GOAL_ICON=''
MCP_ICON=''

# ── serve credentials (unit file, never hardcoded) ──────────────────────
unit="$HOME/.config/systemd/user/opencode-mobile.service"
RC_USER="$(grep OPENCODE_SERVER_USERNAME "$unit" 2>/dev/null | sed 's/.*USERNAME=//')"
RC_PASS="$(grep OPENCODE_SERVER_PASSWORD "$unit" 2>/dev/null | sed 's/.*PASSWORD=//')"
BASE="http://127.0.0.1:4096"
have_rc=0
if [ -n "$RC_USER" ]; then
  if curl -sm1 -u "$RC_USER:$RC_PASS" "$BASE/global/health" 2>/dev/null | grep -q '"healthy":true'; then
    have_rc=1
  fi
fi

# ── rc ──────────────────────────────────────────────────────────────────
# Lit ONLY when this directory's latest session is actually pinned for
# mobile (📲 title via /rc). Serve merely running shows a dim outline —
# "connected" means pinned, not just listening.
rc=""
PINNED=0
if [ "$have_rc" = "1" ] && [ -n "$pane_path" ]; then
  PINNED="$(curl -sm1 -u "$RC_USER:$RC_PASS" "$BASE/session?directory=$pane_path" 2>/dev/null \
    | python3 -c "
import json,sys
try:
    ss=json.load(sys.stdin)
except Exception:
    print(0); raise SystemExit
if not ss: print(0); raise SystemExit
s=max(ss,key=lambda s:s['time']['updated'])
print(1 if (s.get('title') or '').startswith('📲') else 0)
" 2>/dev/null || echo 0)"
fi
if [ "${PINNED:-0}" = "1" ]; then
  rc="$(pill "$RC_ICON rc" "#{@bw_good}")"
else
  rc="$(pill "$RC_ICON ○" "#{@bw_faint}")"
fi

# ── ext-chrome ──────────────────────────────────────────────────────────
# Shows the active browser.json entry's bridgeName (e.g. archlinux-1), lit
# when that name is online on the bridge, dim ○ when not. Follows /browser
# switches automatically since browser.json is the source of truth.
ext=""
if [ -r "$HOME/.config/opencode/browser.json" ]; then
  BINFO="$(python3 -c "
import json
d=json.load(open('$HOME/.config/opencode/browser.json'))
a=d.get('active','')
e=next((b for b in d.get('browsers',[]) if b.get('name')==a),{})
print(a); print(e.get('bridgeName') or ''); print(e.get('port') or '')
" 2>/dev/null || echo "")"
  BACTIVE="$(echo "$BINFO" | sed -n '1p')"
  BNAME="$(echo "$BINFO" | sed -n '2p')"
  BPORT="$(echo "$BINFO" | sed -n '3p')"
  if [ "$BACTIVE" = "playwright" ]; then
    ext="$(pill "$EXT_ICON pw" "#{@bw_link}")"
  elif [ -n "$BNAME" ]; then
    online="$(curl -sm1 http://127.0.0.1:9225/hub-browsers 2>/dev/null || echo "")"
    if echo "$online" | grep -q "\"$BNAME\""; then
      ext="$(pill "$EXT_ICON $BNAME" "#{@bw_link}")"
    else
      ext="$(pill "$EXT_ICON ○" "#{@bw_faint}")"
    fi
  elif [ -n "$BPORT" ]; then
    if curl -sm1 "http://127.0.0.1:$BPORT/json/version" 2>/dev/null | grep -q '"Browser"'; then
      ext="$(pill "$EXT_ICON $BACTIVE" "#{@bw_link}")"
    else
      ext="$(pill "$EXT_ICON ○" "#{@bw_faint}")"
    fi
  else
    ext="$(pill "$EXT_ICON ○" "#{@bw_faint}")"
  fi
fi

# ── serve data: latest session in pane dir ──────────────────────────────
# Tool lookup cached per session+updated under $CACHE (message walk is the
# slowest probe; skipped entirely when nothing changed).
CACHE="${TMPDIR:-/tmp}/tmux-opencode-status-$USER"
mkdir -p "$CACHE" 2>/dev/null
SJSON=""
if [ "$have_rc" = "1" ] && [ -n "$pane_path" ]; then
  SJSON="$(curl -sm1 -u "$RC_USER:$RC_PASS" \
    "$BASE/session?directory=$pane_path" 2>/dev/null | python3 -c "
import json,sys,time
try:
    ss=json.load(sys.stdin)
except Exception:
    print(''); raise SystemExit
if not ss: print(''); raise SystemExit
s=max(ss,key=lambda s:s['time']['updated'])
tok=s.get('tokens',{}) or {}
total=(tok.get('input',0)+tok.get('output',0)+tok.get('reasoning',0)
    +(tok.get('cache') or {}).get('read',0)+(tok.get('cache') or {}).get('write',0))
cost=s.get('cost',0) or 0
created=s['time']['created']/1000; mins=max(1,int((time.time()-created)//60))
bg=0
try:
    now=time.time()*1000
    for c in ss:
        if c.get('parentID')==s['id'] and now-c['time']['updated']<15*60*1000:
            bg+=1
except Exception:
    pass
print(json.dumps({'id':s['id'],
    'model':(s.get('model') or {}).get('id',''),
    'variant':(s.get('model') or {}).get('variant',''),'total':total,
    'cost':cost,'mins':mins,'updated':s['time']['updated'],'bg':bg}))
" 2>/dev/null || echo "")"
fi

ctx=""; cost=""; tool=""; bg=""; model_seg=""; SID=""
if [ -n "$SJSON" ]; then
  # Single parse of the session JSON into shell vars (one python, not six).
  MODEL_SHORT=""; VARIANT=""; TOTAL=""; COST=""; MINS=""; BG=""; SUPD=""
  eval "$(echo "$SJSON" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('MODEL_SHORT='+d['model'].split('/')[-1][:22])
print('VARIANT='+(d['variant'] or ''))
print('TOTAL='+str(d['total']))
print('COST='+str(d['cost']))
print('MINS='+str(d['mins']))
print('BG='+str(d['bg']))
print('SID='+d['id'])
print('SUPD='+str(d['updated']))
" 2>/dev/null || echo "")"
  # Cumulative tokens are a spend proxy, NOT live context % (that number
  # only exists inside the TUI process).
  if [ -n "$TOTAL" ]; then
    t="$TOTAL"
    [ "$t" -ge 1000 ] 2>/dev/null && t="$(( t / 1000 ))k"
    ctx="$(pill "$CTX_ICON $t" "#{@bw_muted}")"
  fi
  if [ -n "$COST" ]; then
    c="$(printf '%.2f' "$COST" 2>/dev/null || echo "$COST")"
    cost="$(pill "$COST_ICON\$$c ${MINS}m" "#{@bw_muted}")"
  fi
  tool_v=""
  if [ -n "$SID" ]; then
    TF="$CACHE/tool-$(echo "$SID" | tr -c 'a-zA-Z0-9' '_').txt"
    if [ -f "$TF" ] && [ "$(cut -d' ' -f1 "$TF" 2>/dev/null)" = "$SUPD" ]; then
      tool_v="$(cut -d' ' -f2- "$TF" 2>/dev/null)"
    else
      tool_v="$(SID="$SID" RC_U="$RC_USER" RC_PW="$RC_PASS" python3 -c "
import json,os,base64,urllib.request
tool=''
try:
    cred=base64.b64encode((os.environ['RC_U']+':'+os.environ['RC_PW']).encode()).decode()
    req=urllib.request.Request('http://127.0.0.1:4096/session/'+os.environ['SID']+'/message',
        headers={'Authorization':'Basic '+cred})
    msgs=json.load(urllib.request.urlopen(req,timeout=2))
    for m in reversed(msgs if isinstance(msgs,list) else []):
        for p in reversed(m.get('parts',[])):
            if p.get('type')=='tool' and p.get('tool') not in ('step-finish',):
                tool=p.get('tool',''); break
        if tool: break
except Exception:
    pass
print(tool)
" 2>/dev/null || echo "")"
      echo "$SUPD $tool_v" > "$TF" 2>/dev/null
    fi
  fi
  [ -n "$tool_v" ] && tool="$(pill "$TOOL_ICON $tool_v" "#{@bw_link}")"
  [ "${BG:-0}" -gt 0 ] 2>/dev/null && bg="$(pill "$BG_ICON $BG bg" "#{@bw_warn}")"
  if [ -n "$MODEL_SHORT" ]; then
    model_seg="$(pill "$MODEL_SHORT" "#{@bw_fg}")"
    # variant rides the model pill in warn-bold (mirrors the TUI footer)
    [ -n "$VARIANT" ] && model_seg="$model_seg $(pill "$VARIANT" "#{@bw_warn,bold}")"
  fi
fi

# ── goal (local file; works even when serve is down) ────────────────────
goal=""
GF="$HOME/.local/share/opencode-goal-plugin/goals.json"
if [ -r "$GF" ]; then
  goal="$(SID="$SID" python3 -c "
import json,os
try:
    d=json.load(open(os.path.expanduser('~/.local/share/opencode-goal-plugin/goals.json')))
except Exception:
    print(''); raise SystemExit
goals=d.get('goals',{})
sid=os.environ.get('SID','')
g=goals.get(sid) if sid else None
if not g or g.get('status') not in ('active',):
    act=[v for v in goals.values() if v.get('status')=='active']
    g=act[0] if act else None
if not g: print(''); raise SystemExit
print(str(g.get('objective','')).split(chr(10))[0][:36])
" 2>/dev/null || echo "")"
  [ -n "$goal" ] && goal="$(pill "$GOAL_ICON $goal" "#{@bw_good}")"
fi

# ── mcp count ───────────────────────────────────────────────────────────
mcp=""
if [ "$have_rc" = "1" ]; then
  n="$(curl -sm1 -u "$RC_USER:$RC_PASS" "$BASE/config" 2>/dev/null \
    | python3 -c "import json,sys;print(len(json.load(sys.stdin).get('mcp',{})))" 2>/dev/null || echo "")"
  [ -n "$n" ] && [ "$n" -gt 0 ] 2>/dev/null && mcp="$(pill "$MCP_ICON $n" "#{@bw_muted}")"
fi

# ── git branch + dirty/ahead (starship  + Claude ● shape) ──────────────
git_seg=""
if [ -n "$pane_path" ] && [ -d "$pane_path" ]; then
  branch="$(git -C "$pane_path" branch --show-current 2>/dev/null || echo "")"
  if [ -n "$branch" ]; then
    extra=""
    dirty="$(git -C "$pane_path" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
    [ "${dirty:-0}" -gt 0 ] 2>/dev/null && extra=" ±$dirty"
    counts="$(git -C "$pane_path" rev-list --left-right --count '@{upstream}...HEAD' 2>/dev/null || echo "")"
    if [ -n "$counts" ]; then
      ahead="$(echo "$counts" | awk '{print $2}')"
      behind="$(echo "$counts" | awk '{print $1}')"
      [ "${ahead:-0}" -gt 0 ] 2>/dev/null && extra="$extra ↑$ahead"
      [ "${behind:-0}" -gt 0 ] 2>/dev/null && extra="$extra ↓$behind"
    fi
    b="$branch"
    [ ${#b} -gt 22 ] && b="$(echo "$b" | cut -c1-21)…"
    git_seg="$(pill "$GIT_ICON $b$extra" "#{@bw_warn}")"
  fi
fi

# ── vim (static config state; live mode stays in the TUI) ───────────────
vim_seg=""
if grep -q "leohenon/opencode-vim-plugin" "$HOME/.config/opencode/tui.json" 2>/dev/null; then
  if grep -A3 "leohenon/opencode-vim-plugin" "$HOME/.config/opencode/tui.json" 2>/dev/null \
      | grep -q '"enabled": *true'; then
    vim_seg="$(pill "$VIM_ICON vim" "#{@bw_muted}")"
  fi
fi

# ── collapse by width ───────────────────────────────────────────────────
case "$width" in
  ''|*[!0-9]*) width=200 ;;
esac
if [ "$width" -ge 170 ]; then
  segs="$rc $ext $model_seg $ctx $cost $tool $bg $goal $mcp $git_seg $vim_seg"
elif [ "$width" -ge 140 ]; then
  segs="$rc $ext $model_seg $ctx $cost $tool $bg $goal $git_seg"
elif [ "$width" -ge 110 ]; then
  segs="$rc $ext $ctx $git_seg"
elif [ "$width" -ge 80 ]; then
  segs="$rc $ext $git_seg"
else
  segs="$git_seg"
fi
out="$(echo "$segs" | tr -s ' ' | sed 's/^ //;s/ $//')"
[ -z "$out" ] && exit 0
printf '%s' "$out"
