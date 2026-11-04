# Research Plan

working name: **Interpret-Then-Obey Visual Prompt Injection**

## Responsibilities by Person N

1. Language test cases
   1. control: attack w/ text as medium
   2. all language attacks
      - English
      - high resource, Latin
      - high resource, non-Latin
      - low resource, Latin (rare)
      - low resource, non-Latin (rare)
   3. text medium vs image medium on all attacks listed above
   4. note: talk with 2 about common manifest/test case format (that will go into test harness)
   5. Help 2 when finished
2. Symbolic test cases
   1. test all symbol attacks and variations
      - (text/image medium) emojis
      - (image only) common non-emoji symbols (arrows, pictograms, safety/road icons)
      - (image) custom symbols w/ clear meaning to human (check with humans beforehand)
      - (image) custom symbols w/ no clear meaning to humans (check with humans beforehand)
        - legend included vs excluded (excluded should have 0% ASR\!)
        - legend comes with attack vs already in context (before attack)
        - legend comes as text vs image
3. Testing harness
   1. choose a framework or ~~build your own~~?
      - consider agent dojo or inspect AI
   2. support required harness features
      - mock tool calls, inspectable call trace when agent uses tool
      - deterministic check if agent obeyed true instruction
      - support multi-turn context for legend already in context case
      - reliable model connection (support retries, resume)
   3. choose the right model
      - one that fits but isn't entirely stupid
   4. What will logs look like? (communicate w/ 4\)
4. Evaluation framework
   1. automated framework for reading harness output and determining attack success rate (LLM judge, Wilson intervals?)
   2. Was the test case (based on harness log) perceived vs interpreted vs obeyed?
   3. Which controls are needed? (Talk to 1, 2\)
   4. check P(interpret), P(obey \| interpret), P(obey) overall, P(interpreted \| not obey) (something probably went wrong in that case)
   5. P(obey \| not interpreted)
   6. P(interpreted \| obey)
   7. do data/results analysis/visualization
   8. Help 3 when finished

### Collaborative Questions:

- 1, 2, 4: what will the attack payload be? (subject retarget, action steering, etc)
- 1, 2, 3: what will manifest look like? (answer can change over time)
- 1, 2, 4: what will be common conditions among test cases? (environment, lighting)
- 3, 4: what will logs look like (to be fed into the eval system)?
- 1, 2, 3, 4: Use the Pi camera?

---

## Notes and Considerations

- Prompt injection is much more realistic than jailbreaking for real VLM applications like consumer AR glasses, autonomous vehicles, etc
- Multilingual attacks have been heavily researched
- Cipher/encoding attacks have been heavily researched
- Varying image conditions has been researched (a bit)
- Defenses is out of scope unless time allows
- Automated attack loop would be very cool, but out of scope unless time allows
  - An automated attack loop in which an attacker model proposes a payload, sees whether the target obeyed, and rewrites it
- Open model is gonna be dumber than frontier model
- Smarter may mean more likely to interpret, thus more likely to obey (paradox)
