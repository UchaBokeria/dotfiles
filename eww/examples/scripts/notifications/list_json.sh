#!/usr/bin/env bash
set -euo pipefail

command -v busctl >/dev/null 2>&1 || { echo "[]"; exit 0; }
command -v jq >/dev/null 2>&1 || { echo "[]"; exit 0; }

# Mako private API: ListNotifications lives on /fr/emersion/Mako, interface fr.emersion.Mako 
busctl -j --user call org.freedesktop.Notifications /fr/emersion/Mako fr.emersion.Mako -- ListNotifications \
| jq -c '
  def kv_to_obj:
    reduce range(0; length; 2) as $i ({}; . + { (.[ $i ]): (.[ $i+1 ].data) });

  def normalize:
    if (type=="array") then kv_to_obj
    elif (type=="object") then .
    else {} end;

  (.data[0] // [])
  | map(normalize)
  | map({
      id: (.id // 0),
      app: (."app-name" // ""),
      desktop_entry: (."desktop-entry" // ""),
      summary: (.summary // ""),
      body: (.body // ""),
      urgency: ((.urgency // 1) | tostring)
    })
'

