#!/usr/bin/env bash
set -euo pipefail

# nmcli wifi list & connect usage. :contentReference[oaicite:15]{index=15}

# --escape yes ensures ':' is escaped as '\:' in terse output
nmcli --terse --escape yes --fields IN-USE,SSID,SIGNAL,SECURITY device wifi list 2>/dev/null \
| awk -F: '
  function unescape(s) {
    gsub(/\\:/, ":", s)
    gsub(/\\\\/, "\\", s)
    return s
  }
  BEGIN {
    print "["
    first=1
  }
  {
    inuse = ($1=="*") ? "true" : "false"
    ssid = unescape($2)
    signal = ($3=="" ? "0" : $3)
    sec = unescape($4)
    # base64 for safe passing to scripts
    cmd = "printf %s " quote(ssid) " | base64 -w0"
    cmd | getline b64
    close(cmd)

    if (!first) print ","
    first=0
    printf "{\"in_use\":%s,\"ssid\":\"%s\",\"ssid_b64\":\"%s\",\"signal\":\"%s\",\"security\":\"%s\"}", inuse, escape_json(ssid), b64, signal, escape_json(sec)
  }
  END { print "\n]" }

  function quote(s,    t) { t=s; gsub(/'\''/, "'\''\\'\'''\''", t); return "'\''" t "'\''" }
  function escape_json(s,    t) { t=s; gsub(/\\/,"\\\\",t); gsub(/"/,"\\\"",t); return t }
'
