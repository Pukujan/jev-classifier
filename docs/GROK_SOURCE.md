# Grok research-source capture

This feature makes one bounded OpenRouter Chat Completions call and writes a versioned JSON source artifact. The default requested model is `x-ai/grok-4.1-fast`; `GROK_SOURCE_MODEL` or `--model` can select a different OpenRouter model for source collection. This adapter never classifies, scores, labels, or creates claim-graph entries. Its transcript and citations are untrusted material; deterministic classifier judgments remain on the pinned TypeSafe JEV Decisions path.

## Run one capture

Set `OPENROUTER_API_KEY` in the ignored project `.env` or process environment, then run from the repository root:

```powershell
python scripts/grok_research.py --query "Find primary research on ..." --output artifacts/grok/source-001.json
```

The output path must stay inside the project folder, and the command refuses to overwrite an existing artifact. The command makes no retries. Its request caps output at 1,200 tokens and server tools at one call, five results per search, five total results, and one `max_uses` where supported. It does not enable X search or streaming. A fixed system instruction asks for source capture only and forbids classifier labels/scores; captured text still remains untrusted. Temperature is sent as `0.0` for a repeatable request configuration; provider/model behavior is not thereby guaranteed deterministic.

## Artifact contents and hash

`schemas/v1/grok-source-artifact.schema.json` defines `jev.grok_source.v1`. The artifact stores the exact system instruction, query, and request settings, requested and provider-surfaced model identifiers, response and provider request ids when available, transcript, annotation-backed citations, provider usage, complete decoded response body, retrieval timestamp, and SHA-256 content hash. API keys and authorization headers are never included. The hash is SHA-256 over compact UTF-8 JSON with recursively sorted keys, excluding `metadata` (including `retrieved_at`) and `content_sha256` itself. Provider response fields, including ids, usage, and the raw body, remain part of the hashed source payload.

Citations are copied from provider `url_citation` annotations. URLs must be absolute HTTP(S) URLs with a host; malformed citations fail closed. When the provider supplies no annotations, the artifact records `no_annotations_returned`; it does not mine links from free-form prose. A missing/invalid response id, surfaced model, assistant message, transcript, or malformed usage shape fails closed. If usage is absent, it stays `null`. Error text excludes credentials and response bodies.

Artifacts include queries and raw provider responses. Keep them local when they contain private research context; do not commit them by default. For reproduction without network access, use the mocked fixture and `python -m pytest tests/test_grok_research.py -q`.

## Provider note

OpenRouter documents `openrouter:web_search` as a beta Chat Completions server tool. Its docs describe citations as `url_citation` annotations and search usage as `usage.server_tool_use.web_search_requests`; Grok 4+ supports native provider search. Provider behavior may change, so request settings and the raw response are preserved. See the [OpenRouter Web Search guide](https://openrouter.ai/docs/guides/features/server-tools/web-search).
