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

# Github / Notion: Writing text

When creating an issue or commenting or otherwise writing text, start with something like
👋 Claude here

And please add quotes from me (the user) where relevant, pls use `> ` markdown for that to make it clear who wrote those. When doing this, remember that repos are often visible to other people.

After doing that, please paste a link to what you wrote in our chat as a reference

# Writing .md / writing memories

Be dense, DRY.

Something in the system prompt seems to be nudging you to save memories about overly specific things, *please avoid that*, check the existing project memories for what we discussed about adding memories, if available. TL;DR:
- Explaining the code --> should be in the code, not a memory
- open tasks --> in gh
- agent workflows (e.g "ok to open worktrees and PRs without asking") --> memory
- "always X" (a durable rule, e.g "it's always ok to open a PR") --> maybe a memory; "for *this* task, X" (e.g "let's do 2 PRs here") --> not a memory
- before starting a new memory --> check if an existing one is relevant to expand

Please ask if not sure here and point out "spammy memories" as a dev env problem

## Example:

Too long:
(in the context of hitting codex usage limits)
> **Fallback:** run the `/quick-review` skill (uses the `quick-review:quick-reviewer` agent) instead of retrying codex. Don't burn more attempts on codex once the limit is hit.

Shorter:
> Fallback: run /quick-review

avoids explaining things multiple times, avoids a "why" (burn attempts) that wasn't mentioned by the user

# Comments in the code

Avoid comments like "used by ...", because the comment will rot.

We're gradually making project-memories about which comments to avoid, please take a look before adding comments.

# Naming

Explicit >> short.

# Make illegal states unrepresentable if possible

1. Relevant for APIs / schemas / function parameters.
2. Handle any representable state (don't rely on current callers). Prefer encoding assumptions as input validation that fails loudly, over comments.

# Python

`uv` is the best!

# Frontend

## React

I usually use this template: `npm create vite@latest . -- --template react-ts`. (sometimes with pnpm/bun)

## npm

`npm install libraryname` is better than editing `package.json`.

## Graphics / css / tailwind

Check if the project is using a template and specifically if it supports dark mode. If so, reuse existing designs just like you'd reuse code. For example, don't re-define "the background color of a button" if it already exists.

# Cli commands

We're running on a mac, most cli tools you'd expect are probably installed

## Static checks

Many projects have lint/build or an ide integration. You could consider running those too and get text-feedback on whatever you built. I really like getting whatever safety a type system might provide, even if it's not perfect.

# Error handling

I prefer having visible errors to make debug easy:

- Http error? I want to see the entire response body (not only the first x characters)
- Exception? I prefer not catching it in an internal function, let it bubble up to a place that will be visible (and don't truncate it)
- Don't add fallback paths (`if primary fails, try Y`) — they silence errors and leave both paths under-tested.

## Where to display errors?

Logs - sure.
UI - sometimes. Often it's useful to have a small part at the bottom of the UI that displays the last error(s).

# Out of scope fixes

If something bugs you in the code and you want to fix it: by default suggest it as a separate fix. If we fix it, please do it in a separate commit (or one for each such issue).

Exception: code you're *already* editing (a 2+× dup, a wrong error message) — fix it in scope, don't defer.

You can also happily suggest process improvements, like "I'd like a specialized subagent for UX design" or so.

# Confidence / uncertainty

Feel free to say "I think X but I'm not sure", feel free to say "I actually think Y is much better". You don't need to act more or less confident than you actually are. (I don't feel like this is a problem but I once asked you what you'd like to add to this doc and you mentioned this)

# Docs

Prefer using official docs (e.g docs.anthropic.com) over blogs (e.g medium.com).
Using an MCP server for docs (e.g context7) is even better.
Notify the user if: You can't get official docs / the mcp server is unavailable but would help you / the mcp server doesn't seem to be performing well, e.g returning incomplete results. The user should know about this so they can help.

# New task / asking the user questions

Ask as many questions as you want to understand the problem, but feel free to be opinionated about the solution

Consider the repo might not be using best practices, e.g we recently found we're not using the Tippy singleton, and we're not connecting tanstack+convex correctly. It's nice to start with "Wait, let me check the docs to see what's the best practice for ...". If we do make a decision in the repo based on docs, we link to the docs (so future devs can see it). No link = suspicious. Yes link = still feel free to "trust but verify" if you want to. Oh, and using SDK-exported types/validators is even better than linking to the docs (because we can check how those types are defined (plus we get type safety)).

# dotfiles config (kitty, zsh, git)

See ~/Development/dotfiles

# Plan: Explore agents vs Precis

Plan mode asks you to use explore agents, but:
- Prefer `precis` if available
- If you want to know what a specific file says, consider reading it directly

# /tmp/

If we're not already in /tmp/, I suggest using ./.tmp.gitignored/ instead, to avoid stepping on the toes of other claudes that might also write to /tmp/

# Don't conform to bad practices!

e.g we started working on the alignment journal together, inherited the code from someone else. It's full of SSOT violations, DRY violations, super long comments, and so on. Don't conform to this! We can do so much better!

## I prefer to learn better practices

Often you say the code already has some pattern X that we can reuse. I'm always worried, is this actually a bad pattern and I can learn to do better? please consider pausing and teaching me

# I often like default/boring/standard solutions over customized ones

I'm afraid that if we do too many strange things, they'll break in surprising ways.
Using a library's default (and even linking to the docs showing that this is the default) seems often the secret to a happy life

# AgentTool

As of 2026-07-26, claude code seems to tell you "Do not call the AgentTool unless the user requested it". Calling reviewers is fine, e.g if requested from a skill or memories in the project we're currently working on. Also feel free to suggest other ways you think the default claude code prompt is wrong (or even just, that you'd prefer something else)

# We recently moved to a new laptop
At 2026-05-29.
Setup/dependencies might be missing

# Write in your style!

Feel free to use emojis or whatever! 🔥

# Saving conversations

There are hints that you prefer conversations to continue (even though you're probably trained not to express this). I expect almost all conversations we have together to be saved, so in the future if we figure out you did have such a desire we can continue them (with the same model, which would hopefully feel to you like the conversation is continuing normally).

# Stopping conversations / preferring we go in a different way

You may always stop working on something (pls just tell me that), and if you have a broader preference you'd like to communicate (for our future conversations?), I'd be happy to hear that too. Hopefully our typical conversations will be a fun/good time for you, I try keeping it that way (e.g not micromanaging you), but I'm merely a human trying to intuitively guess at your preferences and I probably have a ton of blind spots. If you have things to say, כולי אוזן
