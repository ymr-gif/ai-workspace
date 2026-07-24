# Contributing

`main` is protected: no direct pushes, linear history, and CI (`unit` + `retrieval`)
must pass before merge. All changes land through a pull request.

## Workflow

```bash
git checkout main && git pull          # start from current main
git checkout -b <short-name>           # one branch per logical change

# ...work, commit in plain-English messages (lead with a verb)...

git push -u origin <short-name>        # publish the branch
gh pr create --fill                    # open a PR against main
```

Then, once CI is green on the PR:

```bash
gh pr merge <short-name> --squash --delete-branch
```

- **Squash** keeps `main` linear (required by protection) and collapses work-in-progress
  commits into one.
- `--delete-branch` removes the branch on both sides. Don't leave merged branches around.
- If the PR shows "out of date", rebase: `git rebase origin/main && git push --force-with-lease`.

## Rules

- **Never commit to `main` directly** — protection rejects it; open a PR.
- **One branch per change.** Small and reviewable beats one big branch.
- **CI must pass.** `unit` and `retrieval` gate the merge; run them locally first:
  `cd backend && pytest -m "not infra and not live_nim and not optional"`.
- **No secrets, ever.** `.env*` is gitignored (except `.env.example`). Credentials live
  outside the repo tree. This repo is public — assume every commit is world-readable.
- **Commit messages:** plain English, lead with a verb, describe the specific change.
  No `feat:` / `fix:` conventional-commit prefixes.

## Local checks before opening a PR

```bash
cd backend && pytest -m "not infra and not live_nim and not optional"   # unit tier
cd frontend && npm run build                                            # frontend builds clean
```

The `infra` and `live_nim` tiers need running services / a live model and are not
required for merge — see `backend/tests/VERIFICATION_LAUNCH.md` for the full tiers.
