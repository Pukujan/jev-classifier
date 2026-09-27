# System design for the README

The page uses the target repository's technical path at reader height:

```mermaid
graph TD
A[Untrusted transcript] --> B[One source fragment]
B --> C[TypeSafe JEV decision]
C --> D[Validated claim record]
D --> E[Template paper draft]
D --> F[Explicit-topic consolidation]
F --> E
```

Adjacent contract summary:

| Step | Current component | Boundary |
| --- | --- | --- |
| Capture | Grok/OpenRouter source module | Transcript and citations remain untrusted. |
| Select | Caller provides one fragment and closed options | Raw transcripts are not automatically extracted and grouped into claim records. |
| Judge | TypeSafe JEV Decisions | No other model may provide semantic classifier labels. |
| Record | Python normalization and legacy M5 claim builder | M5 does not parse timestamp strings, validate time order, resolve evidence references, or verify surfaced model identity end to end. |
| Consolidate | Deterministic M8 module over already-formed claims | Requires explicit topics; validates its bitemporal inputs and preserves conflict instead of choosing by vote. |
| Render | Python paper assembler | Six required sections plus optional deterministic Synthesis from supplied topic records; no narrative prose or citation verification. |

The flow description is drawn from src/jev_classifier/sources/grok.py, src/jev_classifier/classify.py, src/jev_classifier/normalize.py, src/jev_classifier/consolidate.py, and src/jev_classifier/paper/assemble.py. The detailed module contract is owned by docs/SYSTEM_SPEC.md and its tracking issue; this README task does not change that contract.
