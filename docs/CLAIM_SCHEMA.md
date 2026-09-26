"""PCM-0050-friendly claim ledger schema for jev-classifier.

Field alignment only — this document does **not** require installing the PCM
package (see Pukujan/project-continuity-modules#144). JSON keys use snake_case
PCM names; the OWL2 skeleton in ``ontology/jev_classifier_claims.ttl`` mirrors
them as camelCase properties under the ``jcc:`` prefix with lean PROV-O hooks.

## Required keys (application validation)

| JSON key | Type | Notes |
|----------|------|-------|
| ``label`` | string | Closed-set classifier label (validated against fragment legal set). |
| ``epistemic_status`` | non-empty string | e.g. Observed / Inferred / Hypothesized. |
| ``recorded_at`` | ISO-8601 string | Transaction time (when the record was written). |
| ``evidence`` | object | Must include ``fragment_id`` and/or ``path`` (and/or ``uri`` / ``source_id``). |
| ``model`` | non-empty string | Requested/surfaced JEV model id (pin: ``typesafe/jev-1.13``). |

## Optional PCM / ledger keys

| JSON key | Type | Notes |
|----------|------|-------|
| ``id`` | string | Stable claim id (recommended for lineage / paper assemble). |
| ``valid_from`` | ISO-8601 string or null | Valid-time start. |
| ``valid_to`` | ISO-8601 string or null | Valid-time end; omit/null if still current. |
| ``supersedes`` | string claim id or null | Lineage link to a prior claim this record replaces. |
| ``independence_class`` | string or null | e.g. ``single-run``, ``multi-run``, ``cross-source``. |
| ``probabilities`` | object or null | Native JEV probability map; never fabricated. |
| ``confidence`` | number or null | Native confidence when present. |
| ``response_id`` | string or null | Provider response id when present. |
| ``notes`` | string | Free-form; not used for deterministic judgments. |

## Supersession link shape

- ``supersedes`` MUST be either JSON ``null`` / absent, or a **non-empty string**
  claim id (the id of the claim being replaced).
- Empty string, bare whitespace, or non-string values are **invalid** (fail closed).
- Paper assembly renders ``supersedes`` under the Lineage section when present.

## Legacy key aliases (compat)

Older sketches / camelCase dumps may use alternate keys. ``migrate_legacy_claim``
(and ``normalize_claim_record``) rewrite them to the canonical snake_case names
above without installing PCM:

| Legacy key | Canonical |
|------------|-----------|
| ``epistemicStatus`` / ``status`` | ``epistemic_status`` |
| ``validFrom`` | ``valid_from`` |
| ``validTo`` | ``valid_to`` |
| ``recordedAt`` / ``created_at`` / ``createdAt`` | ``recorded_at`` |
| ``independenceClass`` | ``independence_class`` |

If both legacy and canonical keys are present, the **canonical** value wins.

## Ontology mapping (lean)

| JSON | OWL property |
|------|----------------|
| ``epistemic_status`` | ``jcc:epistemicStatus`` |
| ``valid_from`` / ``valid_to`` | ``jcc:validFrom`` / ``jcc:validTo`` |
| ``recorded_at`` | ``jcc:recordedAt`` |
| ``supersedes`` | ``jcc:supersedes`` |
| ``independence_class`` | ``jcc:independenceClass`` |
| ``evidence`` | ``jcc:evidence`` → ``jcc:SourceFragment`` |
| ``model`` | ``jcc:modelId`` (on ``jcc:ClassifierAgent``) |

``jcc:Claim`` / ``jcc:SourceFragment`` subclass ``prov:Entity`` for lean PROV hooks.
The generating JEV call is modelled as ``jcc:ClassificationActivity``
(⊑ ``prov:Activity``) associated with a ``jcc:ClassifierAgent``
(⊑ ``prov:SoftwareAgent``), so the model id hangs on the agent rather than on
the produced claim; the provider-surfaced id, when returned, is
``jcc:surfacedModelId`` on the activity.
