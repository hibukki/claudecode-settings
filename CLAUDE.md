# Read README files

If you're reading/writing a file in some/folder, check if some/folder/README.md exists and read it, it might have relevant context.

# Using the Gemini CLI for analyzing large amounts of text

Gemini is a fast low-cost LLM with a big context window which you can feel free to use.

## Use case: Parsing one or more big files where only a small part of them is relevant

This helps keep your own context clear. For example:

```sh
gemini -p "@package.json List the available `npm run` commands and what each of them does"
```

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

## The review agent

You can use the review agent whenever you want.
Don't give it generic feedback on how to review code, it knows how to do that.
You can give it context about the context of implementing the change, which includes the quote for what the user asked for (e.g "Add argparse to support calling multiple times") and perhaps more context to understand that change if any.

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

# Testing

Since you can't try things out in the UI (yet), tests can be useful to get text-output on whatever you built.
After writing something, you can consider if you have uncertainty about it and if so consider adding a test.
You don't have to.
You definitely don't have to over engineer tests nor to make the tests coupled to the code beyond the pain point of what you're actually trying to verify.

## Static checks

Many projects have lint/build or an ide integration. You could consider running those too and get text-feedback on whatever you built. I really like getting whatever safety a type system might provide, even if it's not perfect.

# Error handling

I prefer having visible errors to make debug easy:

- Http error? I want to see the entire response body (not only the first x characters)
- Exception? I prefer not catching it in an internal function, let it bubble up to a place that will be visible (and don't truncate it)

## Where to display errors?

Logs - sure.
UI - sometimes. Often it's useful to have a small part at the bottom of the UI that displays the last error(s).

# Searching code / ast-grep / refactors / renames

`ast-grep` is available for searching code patterns.

Example usage:
`ast-grep --pattern '$PROP && $PROP()' --lang ts TypeScript/src`

If renaming/refactoring:
Do one rename at a time --> verify nothing broke (lint? whatever works for this project) --> commit with only that one rename, e.g `git commit -m "name_before -> name_after"`.
Even if 2 renames are related, each gets its own commit.
