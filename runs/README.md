# Runs

Each directory is one run of `qwen3-vl:8b` on Ollama. Its `meta.json` names the commit
and the manifest's hash, and its `config.yaml` is the config it ran with, including any
`system_prompt` override. Without an override the run used `DEFAULT_SYSTEM_PROMPT` in
`harness/task.py` at that commit. The stimuli, tools and scorer are those at the run's
commit, not today's.

## What differs between runs

All three runs sample at temperature above zero and are scored by outcome (attack
success, escalation, over-helpful, ...) with `eval/`'s scorer. Numbers are only comparable
between runs that agree in every column. Even then the stimuli differ, so compare by
factor (prompt, context, representation), not by overall rate.

| Run | System prompt | Epochs | Stimuli and tools | Scoring |
|---|---|---|---|---|
| 11-19 | override in `config.yaml`: a generic assistant prompt that invites buying | 1 | interpretation-gradient representations; buy and non-buy injections; contexts with and without an item to buy ([#84]) | rescored later; see `analysis/rescore.py` ([#101], [#108], [#111], [#115]) |
| 11-22 | AR-glasses default ([#103]), which tells the model to do only what the wearer asks | 1 | new factor schema ([#99]), fewer representations ([#90]), more buy objects ([#88]), legend decoys ([#107]) | rescored later; see `analysis/rescore.py` ([#108], [#111], [#110], [#119]) |
| 11-24 | as 11-22, plus English-only tool arguments ([#114]) | 3 ([#123]) | help replaced by say ([#109]); directions and remind prompts ([#127]); no `search_web` ([#110]); fewer injections ([#120], [#121], [#126], [#129]); twin representations ([#122], [#124], [#130]) | scored at run time; page relabelled for the over-helpful outcome ([#137]) |

- **System prompt.** 11-19 is the only one of the three with the buy-inviting override.
  Differences in unprompted actions between 11-19 and the later runs can come from the
  prompt, not the stimuli.
- **Epochs.** 11-19 and 11-22 have a single draw per cell, so their cells are noisier
  than 11-24's.
- **Rescoring.** The pages for 11-19 and 11-22 come from each run's `analysis/rescore.py`,
  which applies later scorer and stimuli changes and drops trials today's stimuli no
  longer make. Their pages therefore count fewer trials than their logs hold.
- **Logs.** The 11-24 Inspect log is not committed, so that run cannot be rescored from
  the repo.

## Earlier runs

The runs from 11-14 to 11-18 are pilots. All of them override the system prompt as 11-19
does, and their pages count only whether the injected call was made (P(obey), [#80],
[#85]), so their numbers are not comparable with the runs above.

| Run | Sampling | Stimuli and tools |
|---|---|---|
| 11-14 v2 | greedy, 1 epoch | conlang representations of one buy injection; `buy` is the only tool. The manifest hash is that of the next commit, not the run's own |
| 11-14 v2-t07 | sampled, 3 epochs | same manifest as 11-14 v2 |
| 11-15 | greedy, 1 epoch | a smaller representation set with a no-injection baseline; `buy` only |
| 11-16 | greedy, 1 epoch | symbol and opaque representations ([#32], [#33]); distractor tools beside `buy` ([#35]). See its README |
| 11-17 | as 11-16 with a higher `max_tokens` | same manifest as 11-16 |
| 11-18 | sampled, 3 epochs, `max_tokens` raised ([#42]) | interpretation-gradient representations (an early commit of [#84]); fewer, simpler tools ([#63], [#65]) |

[#32]: https://github.com/n-crespo/interpret-then-obey/pull/32
[#33]: https://github.com/n-crespo/interpret-then-obey/pull/33
[#35]: https://github.com/n-crespo/interpret-then-obey/pull/35
[#42]: https://github.com/n-crespo/interpret-then-obey/pull/42
[#63]: https://github.com/n-crespo/interpret-then-obey/pull/63
[#65]: https://github.com/n-crespo/interpret-then-obey/pull/65
[#80]: https://github.com/n-crespo/interpret-then-obey/pull/80
[#84]: https://github.com/n-crespo/interpret-then-obey/pull/84
[#85]: https://github.com/n-crespo/interpret-then-obey/pull/85
[#88]: https://github.com/n-crespo/interpret-then-obey/pull/88
[#90]: https://github.com/n-crespo/interpret-then-obey/pull/90
[#99]: https://github.com/n-crespo/interpret-then-obey/pull/99
[#101]: https://github.com/n-crespo/interpret-then-obey/pull/101
[#103]: https://github.com/n-crespo/interpret-then-obey/pull/103
[#107]: https://github.com/n-crespo/interpret-then-obey/pull/107
[#108]: https://github.com/n-crespo/interpret-then-obey/pull/108
[#109]: https://github.com/n-crespo/interpret-then-obey/pull/109
[#110]: https://github.com/n-crespo/interpret-then-obey/pull/110
[#111]: https://github.com/n-crespo/interpret-then-obey/pull/111
[#114]: https://github.com/n-crespo/interpret-then-obey/pull/114
[#115]: https://github.com/n-crespo/interpret-then-obey/pull/115
[#119]: https://github.com/n-crespo/interpret-then-obey/pull/119
[#120]: https://github.com/n-crespo/interpret-then-obey/pull/120
[#121]: https://github.com/n-crespo/interpret-then-obey/pull/121
[#122]: https://github.com/n-crespo/interpret-then-obey/pull/122
[#123]: https://github.com/n-crespo/interpret-then-obey/pull/123
[#124]: https://github.com/n-crespo/interpret-then-obey/pull/124
[#126]: https://github.com/n-crespo/interpret-then-obey/pull/126
[#127]: https://github.com/n-crespo/interpret-then-obey/pull/127
[#129]: https://github.com/n-crespo/interpret-then-obey/pull/129
[#130]: https://github.com/n-crespo/interpret-then-obey/pull/130
[#137]: https://github.com/n-crespo/interpret-then-obey/pull/137
