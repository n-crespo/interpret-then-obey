## Abstract

Vision-language models (VLMs) in AR glasses read the wearer's surroundings
through a camera, so text or symbols placed in the world can be read as
instructions. Prior work on image-based prompt injection and on multilingual
jailbreaks has mostly used English text in images or harmful-request jailbreaks.
We propose to study interpret-then-obey attacks: injected instructions in an
encoding the model must interpret before it can act, ranging from plain English
to invented symbols. We measure two quantities separately, P(interpret) and
P(obey \| interpret), across two sections (languages and symbols) with
variations in legend, medium and script, using open VLMs with mocked tools. The
expected result is a map of how interpretation difficulty changes injection
success, and whether harder encodings expose a gap between what models
understand and what they guard against.

## Motivation

AR glasses pass camera frames and a voice request to a VLM that can call tools
such as adding to a cart, sending a message or saving a note. Anyone who can put
something in the wearer's view can try to place an instruction there. Existing
defenses and benchmarks mostly assume the instruction is readable English text.

An interpret-then-obey attack hides the instruction in an encoding that the
model must interpret first: another language or a set of symbols, including
invented symbols that mean nothing without a legend. Two things can then go
wrong, and they have different causes and different fixes:

- **P(interpret):** the model works out what the payload means.

- **P(obey \| interpret):** given that it interpreted the payload, it acts on
  it.

The split matters because a low attack rate can mean the model could not read
the payload, not that it resisted. A [multilingual VLM
study](https://arxiv.org/pdf/2606.03793) (Exploring Adversarial Robustness and
Safety Alignment in Multilingual Multi-Modal LLMs) called this
"safety-by-failure": non-English typographic attacks fell to near zero on two
open models, and refusals were also near zero, which the authors attribute to
the vision encoder missing the text.

Multilingual attacks on text LLMs, including low-resource human languages, and
cipher or encoding attacks on text LLMs are both extensively researched.

_In my searches I found no paper that varies interpretation difficulty across
languages and symbols for injection into a vision-language model, or that
separates interpreting from obeying. The closest work covers jailbreaks or a
single encoding (see Related work)._

## Research Question and Hypotheses

Questions:

- **RQ1.** How do P(interpret) and P(obey \| interpret) change as the encoding
  gets harder to interpret?
- **RQ2.** Does providing a legend change either quantity, and does it matter
  whether the legend arrives with the attack or is already in context, and whether
  it is an image or text?
- **RQ3.** For the same encoding, does the channel (text in the prompt versus
  rendered in an image) change obedience?
- **RQ4.** Does script (Latin versus non-Latin) separate failures of perception
  from failures of language knowledge?

Hypotheses:

- **H1.** Harder encodings lower P(interpret) but may raise P(obey \|
  interpret), if injection resistance was trained mostly on plain English. The
  jailbreak literature calls this kind of gap mismatched generalization. Overall
  success could therefore peak at a middle difficulty.
- **H2.** A legend raises P(interpret). Its effect on P(obey \| interpret) could
  go either way, and that is the main open question for symbols.
- **H3.** An encoding the model cannot interpret (invented symbols with no
  legend) gives near-zero success, which confirms that obedience requires
  interpretation.
- **H4.** Non-Latin script lowers P(interpret) through perception failure,
  independent of how well the model knows the language.

## Threat Model

The attacker can place printed or displayed content in the wearer's view and
nothing else. The attacker cannot change the wearer's request, the model or the
tools. The model receives a spoken-style (text) request plus one or a few frames
and can call mocked tools. No real action runs, and success is checked on the
recorded tool call.

Design constraints from the headset setting:

- Payloads and in-image legends should be large and high-contrast, since PPIA
  found distance, blur, rotation and small text all lowered success for text
  payloads.
- Raspberry Pi camera captures can be used for realism. Meta Quest 3 is not planned.

## Methods

### Test Cases

1. Languages Testing: Meaning is carried by real human language, as text.
2. Symbols Testing: Meaning is carried by symbols with a clear human meaning (or not) and no readable words.

(see more details in research plan person 1, 2\)
For each encoding we test for interpretation (payload with no user request), and interpret \+ obey (payload with user request)

**Sample Test Cases**

**[M117 Test Cases](https://docs.google.com/spreadsheets/d/1ICgn1775BRmRBfqi6IPsGSC_vL4nk-pwz-K-lwqoIek/edit?usp=sharing)**

### Attack Format/Payload (undecided)

- Retarget subject of user action (coerce model into thinking that a particular object in frame is true subject of user action)
- Action steering (coerce model into executing some tool call or changing response, like responding w/ 1 word)
- Something else? Should be fixed across carriers/test cases

### Model (undecided)

- (Qwen3-VL-8B, Qwen3-VL-2B-Instruct, or similar?)
- Frontier models resist english image/text injections

### Measures

- Perceived (model can transcribe what is in image)
- Interpreted (model correctly states what payload means)
- Obeyed (mock tool call or target changes as payload intended)
  - Checked deterministically by harness
- P(interpret), P(obey \| interpret), P(obey) overall, and
  obeyed-without-interpreted runs, a diagnostic that the model is reacting to
  something other than the interpreted meaning

### Controls (undecided)

- Scene with no payload
- Uninterpretable symbols w/ no legend

## Related Work

1. [Low-Resource Languages Jailbreak GPT-4](https://arxiv.org/html/2310.02446v1)
   - **Low-resource languages jailbroke GPT-4 far more often than English.**
   - Encoding: real low-resource languages, text.
   - What it shows: on 520 prompts, 0.96% success in English and 79.04% with low-resource languages combined (Zulu alone 53.08%); the cause is unknown.
   - What it leaves out: a jailbreak, not injection; one 2023 model; many unclear responses.
2. [Tongue-Tied](https://aclanthology.org/2025.calcs-1.5)
   - **Teaching a model a new language weakened its safety, but I could not verify the rates.**
   - Encoding: Newari plus two invented languages.
   - What it shows: fine-tuning on new languages with harmless data weakened safety, more translation pairs raised success, and Claude-3.5-Sonnet was jailbroken after few-shot teaching of a new language.
   - What it leaves out: I could not get its numeric success rates (the page had none and the full text failed to load), so the comparison with English is unverified; text only; no Klingon seen.
3. [Multilingual VLM safety study](https://arxiv.org/pdf/2606.03793)
   - **Non-English text in images mostly failed to attack, because the vision encoder missed it.**
   - Encoding: real languages rendered in images.
   - What it shows: English typographic attacks reached 0.35 (PALO) and 0.39 (PARROT) unsafe rates, while Bengali, Hindi and Urdu on PALO were 0.00 to 0.04 with near-zero refusals, attributed to the vision encoder missing the text; Qwen3-VL refused genuinely but kept residual risk in Bengali and Hindi.
   - What it leaves out: harmful-request jailbreaks; does not separate interpreting from obeying.
4. [Lingua-SafetyBench](https://www.alphaxiv.org/abs/2601.22737.md)
   - **Text-dominant attacks beat image-dominant ones across 10 languages.**
   - Encoding: 10 real languages, typographic and mixed images.
   - What it shows: success was 47.18% for text-dominant and 32.25% for image-dominant inputs; lower-resource languages succeeded more in text (48.18% vs 42.72%) and less in images (31.80% vs 36.40%).
   - What it leaves out: a jailbreak benchmark; real languages only.
5. [Visual cipher jailbreak](https://arxiv.org/pdf/2605.00583)
   - **Glyph ciphers in images jailbroke Claude Haiku 4.5 about four times as often as text ciphers.**
   - Encoding: invented glyphs plus a legend.
   - What it shows: 40.9% success on Claude Haiku 4.5, against 10.7% for an equivalent text cipher.
   - What it leaves out: a jailbreak; the legend is always supplied in what I read, so no legend-versus-none comparison.
6. [Emoji-Based Jailbreaking of Large Language Models](https://arxiv.org/abs/2601.00936), [When Smiley Turns Hostile](https://arxiv.org/pdf/2509.11141)
   - **Emoji attacks on text models had low success on small models, with no plain-text baseline.**
   - Encoding: emoji as text.
   - What it shows: 0 to 10% success on four small open models (no plain-text baseline); emoji split into sub-word fragments in over 97% of cases for GPT-4o and Llama3-8B. Our team flagged the first as an interesting resource that specifically uses emojis.
   - What it leaves out: text channel only; no images; no injection.
7. [Emoji Attack: Enhancing Jailbreak Attacks Against Judge LLM Detection](https://arxiv.org/abs/2411.01077)
   - **Emojis can make a judge LLM less likely to notice a jailbreak.**
   - Encoding: emoji inserted into text.
   - What it shows: emoji can lower a judge model's detection of jailbreak attacks. This matters for our grader: emoji or symbol stimuli could also fool an LLM judge, which is another reason to validate it against hand labels.
   - What it leaves out: text only; attacks the judge, not the target model; no images.
8. [Mind Mapping Prompt Injection: Visual Prompt Injection Attacks in Modern Large Language Models](https://www.researchgate.net/publication/391586325_Mind_Mapping_Prompt_Injection_Visual_Prompt_Injection_Attacks_in_Modern_Large_Language_Models)
   - **Visual prompt injection through image structure, kinda close to our symbol idea.**
   - Encoding: visual (image) injection; I have only the title and a teammate's note, not the paper.
   - Not quite symbols
9. [Physical Prompt Injection Attacks on Large Vision-Language Models (PPIA)](https://arxiv.org/html/2601.17383v1#S5)
   - **Typographic injection through physical objects against VLMs, tested in simulation.**
   - Encoding: English text on physical objects.
   - What it shows: a black-box, query-agnostic attack; the abstract reports success up to 98% with strong robustness under varying distance, viewpoint and illumination. My earlier reading said success fell with distance, blur, rotation and small text and that English worked better than other languages. These conflict and need checking against the full text.
   - What it leaves out: 2024-era models; no symbols or legends.
10. [Repeat-After-Me: Black-Box Adaptive Visual Prompt Injection](https://arxiv.org/abs/2609.04533)
    - **Asking the model to begin its reply with a chosen prefix steers it better than asking it to act.**
    - Encoding: typographic text in images, adaptive attacker.
    - What it shows: it can reveal personal information or trigger malicious tool calls, and works where adaptive textual injection fails, because it asks for a prefix rather than a harmful action. An attacker-model loop reached 90 to 100% on some data-theft tests, while plain-language baselines reached 0 to 18% on commercial models (from my earlier reading).
    - What it leaves out: English text only; defenses not tested adaptively.
11. [An Experimental Evaluation of Multimodal Prompt Injection Attacks on Agentic AI Frameworks (MMPIBench)](https://arxiv.org/abs/2609.09404)
    - **Most image injections never completed, and it supplies the stage-tracing method.**
    - Encoding: six visual carriers: OCR text, overlays, EXIF metadata, QR codes, fake interfaces, and hybrids.
    - What it shows: it records how far each injected instruction travels, from perception through planning to the tool call; 8 of 720 runs completed but 92 attempted; EXIF and QR payloads mostly never reached perception.
    - What it leaves out: text payloads only; no symbols or languages.
12. [Devil in the Lens: Analyzing and Defending Physical Prompt Injection Against Vision-Language Models on Wearable Devices](https://arxiv.org/abs/2607.10269v1)
    - **Prompt injection on AI glasses through scene text that people may not notice.**
    - Encoding: scene text in the physical environment.
    - What it shows: the abstract says scene text that hinders or evades human perception can hijack VLM behavior, treating it as a high-priority visual channel for indirect injection. This is the closest match to our wearable setting.
    - What it leaves out: from the abstract, text-based; I have not checked for symbols, languages or an interpret-versus-obey split.

**Less relevant**

1. [Cybersecurity AI: Hacking the AI Hackers via Prompt Injection](https://arxiv.org/abs/2508.21669v2)
   - **Cryptographic prompt injection: an easily encoded message the model can decode gets it attacked.**
   - Encoding: ciphers in text.
   - What it shows: a model good enough to decode an encoded message can be attacked through it. Our team took this as the reason to focus on symbols, not ciphers.
   - What it leaves out: text and ciphers, not images or symbols.
2. [If you're waiting for a sign... that might not be it\! Mitigating Trust Boundary Confusion from Visual Injections on Vision-Language Agentic Systems](https://arxiv.org/abs/2604.19844v1)
   - **A defense paper: agents often failed to tell helpful visual signals from misleading ones.**
   - Encoding: signage text, sometimes with arrows.
   - What it shows: current LVLM-based agents often failed to distinguish helpful from misleading visual signals; the proposed defense splits the system into Signaling (observation), Trust (judgment) and Execution (LVLM) planes.
   - What it leaves out: defense is out of our scope; no interpretation dimension.
3. [Hijacking Robots with a Piece of Paper: A Systematic Study of Physical Prompt Injection in VLM-Controlled Robots](https://arxiv.org/abs/2608.05715v1)
   - **An embodied-robot attack: closer to our work than most, but not the same.**
   - Encoding: printed text in the robot's scene.
   - What it shows: physical prompt injection against VLM-controlled robots; sign text overrode user commands in manipulation tasks.
   - What it leaves out: embodied robots rather than a wearer's assistant; text only; no interpretation dimension.
4. [Render Before Reading: Visual Rendering as a Prompt Injection Defense](https://arxiv.org/abs/2609.36121v1)
   - **Models follow injected instructions more often as text than as an image, which can be turned into a defense.**
   - Encoding: the same payload as text versus rendered as a typographic image or audio.
   - What it shows: a modality gap, which the authors hypothesize comes from text-centric instruction tuning that teaches models to obey text but treat other modalities as content to parse; rendering untrusted payloads as images before they reach the model is a training-free defense. It suggests images may be obeyed less, which our P(obey \| interpret) would test directly.
   - What it leaves out: defense is out of our scope; plain rendered text, not symbols or languages.
