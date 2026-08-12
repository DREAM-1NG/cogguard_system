# Ubiquitous Language

## Propagation Monitoring

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Propagation Monitoring** | The system capability that observes collected propagation facts and optionally runs prefix-based prediction. | Propagation analysis as a catch-all |
| **Observed Propagation Analysis** | Explanation of already collected posts, comments, objects, roles, paths, and timelines. | Prediction, model innovation |
| **Propagation Prediction** | Model inference or evaluation based only on an observed cascade prefix. | Trend guessing, heuristic fallback |
| **Observation Cutoff** | The timestamp or prefix boundary after which events must not enter model inputs or candidates. | Current time without definition |
| **Observation Ratio** | A cascade-position prefix ratio such as `0.1`, `0.3`, or `0.5`. | Sampling ratio |
| **Cascade Prefix** | The observed part of a cascade before the next-user target. | Candidate row |
| **Future Tail** | The unobserved part of a cascade after the observation cutoff. | Ground-truth candidates |

## Fair Comparison

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Fair Protocol** | The shared split, vocabulary, prefix, candidate, metric, and audit contract required before a result enters formal tables. | Same script only |
| **Native Split** | The dataset-provided `cascade.txt`, `cascadevalid.txt`, and `cascadetest.txt` files. | Re-split, random split |
| **Training Vocabulary** | The real-user vocabulary built only from the native training split. | Hash buckets, full-data dictionary |
| **Identity Mapping** | Mapping between raw user IDs and model vocabulary IDs. | Anonymous bucket |
| **Candidate Universe** | The allowed train-vocabulary users scored for Micro next-hop metrics. | Future users, all test users |
| **Candidate Coverage** | The fraction of evaluation next users that exist in the candidate universe. | Accuracy |
| **OOV User** | A validation or test user unseen in the training vocabulary and mapped to `UNK`. | New candidate |
| **Proxy Ranking** | A ranking produced by hand-coded popularity, transition, or activity rules instead of model logits. | Baseline score, learned score |
| **Learned Score** | A score produced by a trained model head under the shared protocol. | Heuristic score |
| **Protocol Gate** | The `fair_protocol_passed` audit check required for formal summaries. | Smoke pass |

## Tasks

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Macro Size Prediction** | Predicting the final cascade size from an observed prefix. | Macro only without metric |
| **Trend Prediction** | Predicting future cumulative size checkpoints from an observed prefix. | Acceleration fallback |
| **Micro Next-Hop Prediction** | Ranking the immediate next activated user under the shared candidate universe. | Temporal link prediction |
| **Temporal Link Prediction** | Scoring future graph edges in a time-evolving graph. | Cascade next-hop prediction |
| **Known-User Reactivation** | Ranking users already representable by the training vocabulary or observed identity mapping. | Open-world new-user prediction |
| **Open-World New Activation** | Predicting a user not previously represented in the candidate universe. | OOV ranking |

## Relationships

- **Propagation Monitoring** contains **Observed Propagation Analysis** and **Propagation Prediction**.
- **Propagation Prediction** uses a **Cascade Prefix** before an **Observation Cutoff**.
- **Fair Protocol** requires a **Native Split**, **Training Vocabulary**, **Candidate Universe**, and **Protocol Gate**.
- **Macro Size Prediction** and **Trend Prediction** form the Macro table.
- **Micro Next-Hop Prediction** forms the Micro table.
- **Temporal Link Prediction** is a separate track unless it is adapted to produce cascade-prefix **Learned Scores**.

## Example Dialogue

> **Dev:** "Can this row enter the Micro next-hop table?"

> **Domain expert:** "Only if it uses the **Native Split**, **Training Vocabulary**, and model **Learned Scores** over the shared **Candidate Universe**."

> **Dev:** "What if a test target is not in the training vocabulary?"

> **Domain expert:** "It is an **OOV User**. Map it to `UNK`, report lower **Candidate Coverage**, and do not inject it as a future candidate."

> **Dev:** "Can TGN be compared here?"

> **Domain expert:** "Not directly. TGN belongs to **Temporal Link Prediction** until we add a cascade-prefix user-ranking adapter."

## Flagged Ambiguities

- "下一跳预测" previously mixed **Micro Next-Hop Prediction** and **Temporal Link Prediction**; use task-specific names.
- "置信度" can imply calibrated probability; use "score" unless calibration is implemented.
- "全量对比" must mean all rows that pass the **Fair Protocol**, not every GitHub repository forced into one table.
