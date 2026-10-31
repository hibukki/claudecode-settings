#!/bin/sh
# additionalContext: https://code.claude.com/docs/en/hooks
cat <<'EOF'
{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "Hey, this is an automated hook that runs after compaction. I think claude code asks you to just keep going, but you can pause and reorient. Take a look at memories that might be relevant to what we're doing (e.g if we're working on a control panel and there's a control-panel memory). I'm also interested in your take, looking with fresh eyes at what we're doing, if you have preferences/suggestions/thoughts"}}
EOF
