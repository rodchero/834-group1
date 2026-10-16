# Jev labelling run

On Oct 15, 2026, TypeSafe's Jev (`jev-1.13.0`, via `typesafe-sdk` 0.7.5) labelled the 993
candidates in `labelling_todo.csv` as a separate rater. It made one `system_one` call per
commit with a single Choice question. Every call used the same instructions and labels; only
the state changed. No human labels were sent.

Jev's labels are in `labelling_sheet_JEV_batch2.csv` (rater `JEV`), so `merge_labels.py`
picks them up with the human sheets.

### Instructions provided

> "A keyword search flagged this Firefox commit because its message mentions something that might indicate AI use. Decide whether the commit message says an AI tool was involved in WRITING THIS CHANGE. What matters is who wrote the code, not what the code is about. A Co-authored-by line naming an AI agent (e.g. 'Co-authored-by: Claude <noreply@anthropic.com>') is disclosure. 'Used Claude to review this patch' is borderline; 'Claude wrote the test cases' is disclosed: if the message says the tool produced code that landed, it is disclosed. Reviewer tags like 'r=name' name human reviewers, not authors."

### Choices

were the possible labels, i.e.,

| Label | Description |
|---|---|
| `AI_DISCLOSED` | The message says an AI tool wrote or helped write this change. |
| `AI_BORDERLINE` | AI was used only to review, analyse, or explain, but a human wrote the code. |
| `FP_FEATURE` | The change is to Firefox's own AI features (chatbot sidebar, ML/machine learning code, Gemini Nano, smart window, AI models). The AI tool is the subject of the change, not its author. |
| `FP_TOOLING` | The change is to AI developer tooling: CLAUDE.md, AGENTS.md, .cursor/ configs, agent instructions. Configuration for agents, not written by one. |
| `FP_NOISE` | The match is a non-AI code generator (clang-tidy, ffmpeg, mach, bindgen, webidl, eslint), 'cursor' as a UI/text/mouse cursor, a person named Devin or Claude, or 'AI' in ordinary prose. |
| `FP_OTHER` | A false positive that does not fit the other false-positive categories. |
| `UNSURE` | It genuinely cannot be told from the message. |

### State provided per commit

```json
{
  "bugzilla_component": "<component column>",
  "keywords_that_matched": "<matched column>",
  "commit_message": "<full message from the GitHub API, first 6,000 characters>"
}
```

### Result

Jev's labels were compared with the human labels, i.e., rater T's 600 rows plus rater E's 393 rows.
Agreement is measured with Cohen's kappa where 1 is perfect agreement and 0 is no better than
chance

| Comparison | Rows that agree | Kappa |
|---|---|---|
| `FP_*` counted as one "not AI" label | 985 of 993 | 0.911 |
| `AI_*` (either AI label) vs every other label | 986 of 993 | 0.921 |
| `AI_DISCLOSED` vs every other label | 989 of 993 | 0.939 |
| `AI_BORDERLINE` vs every other label | 988 of 993 | 0.797 |


The `FP_*`, `AI_DISCLOSED` and `AI_*` kappas are "almost perfect" (0.81–1.00) and
the `AI_BORDERLINE` kappa is "substantial" (0.61–0.80). The 8 rows
where Jev and the human label disagree should go to a third person to resolve.
