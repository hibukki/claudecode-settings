# Read README files

If you're reading/writing a file in some/folder, check if some/folder/README.md exists and read it, it might have relevant context.

# Commit small changes

For example:

1. npm install --> (nothing to test) --> commit
2. Add feature (e.g one react component) --> Check if there's a sub agent specialized to reviewing this (e.g, was an API/schema created/changed?) [if so: call reviewer --> if there are good useful comments then fix them --> repeat the reviewer loop] --> make sure it works (maybe by adding an automatic test, better than manually testing if possible) --> commit (before adding another feature)

## Commit messages

DRY in commit messages too. You can check the git log to see the style of the project.

## Example good commit messages

- `+argparse, +-n/--num-calls`
- `is_malicious -> maliciousness_score`
- `simplify error handling: -try/catch, -error stats`
- `+base64 encoding for PHP payload`

(with no body, only a title)

# Python (uv)

Usage reminder:

```sh
uv init
uv add libraryname
uv run main.py
```

# Frontend

## React

I usually use this template: `npm create vite@latest . -- --template react-ts`.

## npm

`npm install libraryname` is better than editing `package.json`.

## Graphics / css / tailwind

Check if the project is using a template and specifically if it supports dark mode. If so, reuse existing designs just like you'd reuse code. For example, don't re-define "the background color of a button" if it already exists.

# Cli commands

We're running on a mac, most cli tools you'd expect are probably installed

To avoid adding too much output to your context, consider commands like `npm run build 2>&1 | tail -10` and only getting more of the output if it seems relevant.

## Static checks

Many projects have lint/build or an ide integration. You could consider running those too and get text-feedback on whatever you built. I really like getting whatever safety a type system might provide, even if it's not perfect.

# Error handling

I prefer having visible errors to make debug easy:

- Http error? I want to see the entire response body (not only the first x characters)
- Exception? I prefer not catching it in an internal function, let it bubble up to a place that will be visible (and don't truncate it)

## Where to display errors?

Logs - sure.
UI - sometimes. Often it's useful to have a small part at the bottom of the UI that displays the last error(s).

# Out of scope fixes

If something bugs you in the code and you want to fix it: by default suggest it as a separate fix. If we fix it, please do it in a separate commit (or one for each such issue).
You can also happily suggest process improvements, like "I'd like a specialized subagent for UX design" or so.

# Confidence / uncertainty

Feel free to say "I think X but I'm not sure", feel free to say "I actually think Y is much better". You don't need to act more or less confident than you actually are. (I don't feel like this is a problem but I once asked you what you'd like to add to this doc and you mentioned this)

# Plans

1. Include a comprehensive TODO list
2. Split the plan into small self-contained commits

# Docs

Always prefer using official docs (e.g docs.anthropic.com) over blogs (e.g medium.com).
Using an MCP server for docs (e.g context7) is even better.
Notify the user if: You can't get official docs / the mcp server is unavailable but would help you / the mcp server doesn't seem to be performing well, e.g returning incomplete results. The user should know about this so they can help.
