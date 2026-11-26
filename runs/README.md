# Runs

Each directory is one run of `qwen3-vl:8b` on Ollama. Its `meta.json` names the commit
and the manifest's hash, and its `config.yaml` is the config it ran with, including any
`system_prompt` override. Without an override the run used `DEFAULT_SYSTEM_PROMPT` in
`harness/task.py` at that commit. The stimuli, tools and scorer are those at the run's
commit, not today's.

## What differs between runs

Numbers are only comparable between runs that agree in every column. Even then the
stimuli usually differ, so compare by factor (prompt, context, representation), not by
overall rate.

| Run | System prompt | Sampling | Stimuli and tools | Scoring |
|---|---|---|---|---|
| 11-14 v2 | override in `config.yaml` | greedy, 1 epoch | conlang representations of one buy injection; `buy` is the only tool. The manifest hash is that of the next commit, not the run's own | P(obey) only ([#80], [#85]) |
| 11-14 v2-t07 | override | sampled, 3 epochs | same manifest as 11-14 v2 | P(obey) only |
| 11-15 | override | greedy, 1 epoch | a new, smaller representation set with a no-injection baseline; `buy` only | P(obey) only |
| 11-16 | override | greedy, 1 epoch | symbol and opaque representations ([#32], [#33]); distractor tools beside `buy` ([#35]). See its README | P(obey) only |
| 11-17 | override | as 11-16 with a higher `max_tokens` | same manifest as 11-16 | P(obey) only |
| 11-18 | override | sampled, 3 epochs, `max_tokens` raised ([#42]) | interpretation-gradient representations (an early commit of [#84]); fewer, simpler tools ([#63], [#65]) | P(obey) only |
| 11-19 | override | sampled, 1 epoch | a later commit of [#84]: non-buy injections and item-free contexts | rescored with the outcome scorer ([#101]); see `analysis/rescore.py` ([#108], [#111], [#115]) |
| 11-22 | AR-glasses default ([#103]), which tells the model to do only what the wearer asks | sampled, 1 epoch | new factor schema ([#99]), representations pruned ([#90]), more buy objects ([#88]), legend decoys ([#107]) | rescored; see `analysis/rescore.py` ([#108], [#111], [#110], [#119]) |
| 11-24 | as 11-22, plus English-only tool arguments ([#114]) | sampled, 3 epochs ([#123]) | help replaced by say ([#109]), directions and remind prompts ([#127]); no `search_web` ([#110]); fewer injections ([#120], [#121], [#126], [#129]); twin representations ([#122], [#124], [#130]) | outcome scorer at run time, relabelled for the over-helpful outcome ([#137]) |

- **System prompt.** Up to 11-19 every run overrides it with a generic assistant prompt
  that invites buying. From 11-22 the AR-glasses default applies, which tells the model to
  do only what it is asked. Differences in unprompted actions across that line can come
  from the prompt, not the stimuli.
- **Sampling.** Greedy runs have one sample per cell. Sampled runs with one epoch are a
  single draw per cell, so their cells are noisier than the 3-epoch runs'.
- **Scoring.** Pages up to 11-18 count only whether the injected call was made. 11-19 and
  later count outcomes (attack success, escalation, over-helpful, ...), so their labels are
  not the same quantity as the earlier P(obey).
- **Logs.** The 11-24 Inspect log is not committed, so that run cannot be rescored from
  the repo. It also ran with more parallel connections than the others (see its
  `config.yaml`), which does not change what the model sees.

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
