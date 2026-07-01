# CogGuard KT3 Context

This context defines the shared language for KT3 harmfulness assessment. It keeps research, implementation, and evaluation discussions aligned around the same post-level and group-level concepts.

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
