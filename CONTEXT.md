# CogGuard KT3 Context

This context defines the shared language for KT3 harmfulness assessment. It keeps research, implementation, and evaluation discussions aligned around the same post-level and group-level concepts.

Global vocabulary lives in `UBIQUITOUS_LANGUAGE.md`; this file only carries the KT3-local context that is still easier to read in one place. Run **Documentation Sync** through `doc/engineering/system-governance.md` whenever this context changes.

## Language

**Post View**:
A modality-specific interpretation of one post, currently one of Tweet View, Meme View, Image View, or Video View.
_Avoid_: raw feature, channel feature, modality flag

**View Detector**:
A detector that judges one Post View and returns a standard label, score, confidence, evidence, and abstention decision.
_Avoid_: keyword matcher, feature extractor

**View Abstention**:
A detector outcome meaning the view lacks enough decodable evidence to make a confident judgment.
_Avoid_: negative prediction, safe prediction

**Decodable Evidence**:
Content that a View Detector can actually interpret, such as text, OCR, ASR, caption, alt text, or extracted frame/context text. A media URL alone is not Decodable Evidence.
_Avoid_: media exists, URL evidence

For `meme`, `img`, and `video` views, availability means view-specific decodable media evidence exists. Reusing tweet text because a media URL is present is not a valid media-view judgment.

**Effective View**:
A Post View that is available and not abstained, therefore eligible for Majority Vote and View Fusion.
_Avoid_: present modality, raw channel

**Majority Vote**:
A post-level decision rule that counts only confident, non-abstained View Detector labels.
_Avoid_: average score, rule score

**View Fusion**:
A post-level decision rule that combines standardized View Detector outputs into one final harmfulness judgment.
_Avoid_: feature concatenation, manual scoring

**Harmfulness Judgment**:
The final KT3 post-level conclusion: harmful, non-harmful, or uncertain, with harm type and evidence when available.
_Avoid_: toxicity score only, content score only

**Teacher Silver**:
Structured supervision exported from the offline multi-agent teacher as `kt3-teacher-silver-v1`. It contains main axes, stance, confidence, review reasons, evidence spans, trace references, and sample mode.
_Avoid_: training on the full natural-language agent report

**Hard Case**:
A sample routed to the expensive teacher path because it has low confidence, cross-view conflict, claim-linked uncertainty, or other escalation signals. Hard cases keep full trace references.
_Avoid_: every labeled sample, every harmful sample

**Student Main Axis**:
One of the two first-stage encoder targets: `attack_hate_offense` or `misinfo_claim_risk`. These are deployment triage axes, not the full teacher-side taxonomy.
_Avoid_: fine-grained policy subtype, target group, rationale text

**Claim-Linked Stance**:
An auxiliary student head trained only when claim context exists. Samples without claim context must be masked out for this head.
_Avoid_: forcing stance labels on every post

**Selective Routing**:
The student-side `defer` decision that sends uncertain or hard cases back to teacher/human review. It is separate from the semantic risk heads.
_Avoid_: mixing uncertainty into the harmfulness label

**Rationale Boundary**:
Evidence spans may be retained for audit and error analysis, but free-text rationale summaries are not a first-stage student output.
_Avoid_: rationale-generation student
