# Agent notes

## Images in PR descriptions

The repo is private, so PR images can't go on a public host. Put them on the orphan `pr-assets` branch, one folder per PR (`<pr-number>/<file>.png`), and embed them by branch path:

```
https://github.com/n-crespo/interpret-then-obey/raw/pr-assets/<pr-number>/<file>.png
```

- Add a commit on top of `origin/pr-assets` and push it as a fast-forward. Never force-push it, never open a PR for it.
- Don't create per-PR asset branches, and don't link to commit SHAs.
- Never delete `pr-assets` or a PR's folder in it: the PR descriptions that embed them would break.
