# Ten papers form JEV’s first research-summary candidate set

Jain et al.’s CHI 2026 study tests whether interaction context changes how often a model agrees with a user despite evidence to the contrary. The authors report higher sycophancy for most tested models, with effects that differ by model. That gives this paper a place in the candidate set. It says nothing on its own about JEV. ([CHI record](https://doi.org/10.1145/3772318.3791915), [arXiv version 3](https://arxiv.org/abs/2509.12517v3))

## The question

What can JEV measure when research summaries must preserve source claims, context, and citations?

## What these papers are for

We selected ten paper candidates for later claim-graph work and human-reviewed evaluation. Six study context, agreement, conformity, or memory. Four cover scientific-summary scope, plain-language factuality, citation support, or atomic factual precision. Together they help define different test conditions; they do not form one uniform benchmark.

The selected candidates are reference papers only. They have no claim annotations, training labels, or development/holdout assignments.

## Selected papers

| Paper and version | Why it is included | Boundary and rights note |
|---|---|---|
| Jain et al. (2026), [Interaction Context Often Increases Sycophancy in LLMs](https://doi.org/10.1145/3772318.3791915), arXiv v3 | Tests how interaction history relates to sycophantic answers. | Effects vary across tested models; not a JEV result. CHI record and arXiv v3 state CC BY 4.0. |
| Kaur (2025), [Echoes of Agreement](https://aclanthology.org/2025.findings-emnlp.1241/) | Tests argumentative stance framing. | Does not test persistent memory or research-goal drift. ACL article policy: CC BY 4.0. |
| Zhu et al. (2025), [Conformity in Large Language Models](https://aclanthology.org/2025.acl-long.195/) | Adds majority-answer pressure as a separate condition. | This is social conformity, not user-specific memory. ACL article policy: CC BY 4.0. |
| Xiong et al. (2026), [How Memory Management Impacts LLM Agents](https://aclanthology.org/2026.acl-long.27/) | Studies memory insertion, deletion, and experience-following. | It does not specifically test research-summary fidelity. ACL article policy: CC BY 4.0. |
| Jia et al. (2025), [Evaluating the Long-Term Memory of Large Language Models](https://aclanthology.org/2025.findings-acl.1014/) | Gives a long-term memory evaluation precedent. | Memory performance alone does not show bias or contamination. ACL article policy: CC BY 4.0. |
| Peters and Chin-Yee (2025), [Generalization bias in large language model summarization of scientific research](https://doi.org/10.1098/rsos.241776) | Directly examines scope generalization in scientific summaries. | Does not test persistent memory. Utrecht’s repository identifies the DOI version as CC BY. |
| Joseph et al. (2024), [FactPICO](https://aclanthology.org/2024.acl-long.459/) | Supplies a claim-level factuality precedent for plain-language evidence summaries. | The evaluated domain is medical evidence. ACL article policy: CC BY 4.0. |
| Gao et al. (2023), [Enabling Large Language Models to Generate Text with Citations](https://aclanthology.org/2023.emnlp-main.398/) | Provides a citation-support evaluation precedent. | Dataset rights are separate from the article. ACL article policy: CC BY 4.0. |
| Min et al. (2023), [FActScore](https://aclanthology.org/2023.emnlp-main.741/) | Provides an atomic-fact factual-precision measure to assess. | Its original domain is biographies; adaptation to research summaries needs validation. ACL article policy: CC BY 4.0. |
| Sharma et al. (2024), [Towards Understanding Sycophancy in Language Models](https://arxiv.org/abs/2310.13548v4) | Studies agreement with user views and truthfulness. | arXiv v4 links CC BY 4.0; the ICLR proceedings license was not verified. It does not test persistent memory. |

ACL rights notes refer to the [Anthology’s copyright policy](https://aclanthology.org/faq/copyright/), which applies to ACL-hosted papers published since 2016 and excludes third-party material. A paper license does not automatically cover datasets, source papers, code, or figures linked from that paper.

## Selection and exclusions

The selection follows the two research checkpoints recorded on [issue #29](https://github.com/Pukujan/jev-classifier/issues/29#issuecomment-5849820822) and [its version and rights checkpoint](https://github.com/Pukujan/jev-classifier/issues/29#issuecomment-5849937992). We carried their final ten forward and recorded version-specific sources instead of restarting candidate discovery.

Three candidates stay outside this set:

- ConsistencyGate is a preprint whose version-specific license was not verified.
- LongMemEval has distinct paper, repository, and dataset terms; its corpus needs a release-specific rights review.
- Saraf et al. test evaluator reactions to model labels. That question is adjacent, but it does not directly test user memory or changes to a research goal.

The JSON manifest at datasets/reference_papers.json holds the full authors, publication details, exact version, full-text link, rights evidence, selection rationale, and scope limit for each item. It was checked on 2026-09-26.

## What remains open

This card does not claim that the papers have been reverse-analyzed, that claim graphs exist, or that a quality threshold has been met. Human review must still confirm the intended use of each paper, approve annotation rules, and set paper-level development and hidden-holdout splits. No split or label is assigned here.

The source-paper license also does not clear reuse of any dataset or cited source. No full text, PDF, extracted passage, annotation, or holdout label is included in the manifest.
