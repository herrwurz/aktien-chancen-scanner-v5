# V1.4 identity assistant sources and limits

Primary sources checked on 2026-10-22:

- [OpenFIGI API documentation](https://www.openfigi.com/api/documentation): the API is free and public; unauthenticated mapping is supported. `ID_WERTPAPIER` accepts WKN identifiers. The rate-limit table lists 25 requests/minute without a key and at most ten mapping jobs/request. The collector uses serial batches of at most ten and six seconds between batches, at most two HTTP attempts with a fifteen-second timeout. No account, subscription, credential, paid API or key is used. The documentation contains multiple endpoint-specific limits; no higher authenticated allowance is relied upon.
- [OpenFIGI FAQ](https://www.openfigi.com/about/faq): FIGI symbology is provided without fees and the identifier and associated metadata are described as using the MIT open-source license. The FAQ explicitly says third-party proprietary identifiers cannot be returned because of licensing/redistribution restrictions. Request/response correspondence uses response order. Consequently WKN mapping does **not** supply ISIN in this implementation.
- [OpenFIGI terms](https://www.openfigi.com/docs/terms-of-service): public-domain dedication and permission to use, reproduce, distribute and build upon FIGI identifiers. This is the stored license reference; the FAQ explains associated metadata. This does not grant rights to unrelated exchange archives or vendor datasets. Check those separately before importing evidence.

The mapping response supplies FIGI, ticker and provider exchange code. It is a current lookup, not a point-in-time historical identity service. `exchCode` is retained as `provider_exchange_code`; it is never converted into MIC, timezone or currency. ISIN, historical ticker, venue, timezone, currency, listing validity and delisting stay null unless separately supplied by explicit source evidence. Failure to map is not proof of nonexistence or delisting; the API documentation says unlisted equities are excluded by default. No historical completeness is claimed.

## Offline API

`scanner.hebeltrader.identity_assistant.suggest_identity(instrument, source_records, *, run_at)` never performs network access. `run_at` must include a timezone. It returns `candidates`, `reason_codes`, `needed_manual_proof`, `selected=None` and `identity_status='unverified'`. Multiple differing proposals yield `identity_ambiguous`. No proposal is automatically promoted, including dated evidence. Manual review remains necessary through the existing reviewed identity workflow.

Every source record needs `query_wkn`, `provider`, timezone-aware `retrieved_at`, checkable `source_reference`, `license`, `payload`, and `payload_sha256`. The SHA is computed over UTF-8 JSON with sorted keys, separators `(',', ':')`, and `allow_nan=False`. A hash proves byte correspondence, not source authenticity. Caller-provided source references and licenses require human review. Future retrieval/as-of dates and mismatched hashes fail closed. Matching query WKN associates OpenFIGI response order; unassociated records never become candidates. `historical_source` additionally requires `payload.wkn` to match and may explicitly provide `isin`, `historical_ticker`, `venue`, `timezone`, `currency`, `listing_valid_from`, `listing_valid_until`, `delisted_at` and `as_of`. Undated supplied evidence stays `undated_source`. Field evidence points to the raw JSON field, and each candidate retains its source, retrieval, license and payload hash.

## Explicit optional public collection

From the scanner directory:

```sh
PYTHONPATH=. .venv/bin/python -m scanner.hebeltrader.identity_assistant collect \
  --input inventory-manifest.json --output identity-sources-private.json \
  --cache-dir identity-raw-private --provider openfigi --allow-network
```

Input is a list of instrument dictionaries or `{"instruments": [...]}`. Only valid, distinct WKNs are queried, so repeated inventory instruments do not repeat lookup jobs. Output must be new and is created with mode 0600. No inventory/report function invokes this collector implicitly. No live financial lookup was used to create the tests or this documentation; test identifiers and responses are synthetic fixtures only.

The output `records` are explicit offline inputs. Raw HTTP response bytes are cached under their SHA-256 filename with exclusive creation and mode 0600; an existing cache entry must contain identical bytes. Each output record records the raw response SHA, cache basename, source, retrieval time, license and canonical individual-payload SHA. Preserve output together with cache to preserve full provenance. Collection reads are optional and transmit only WKN query values. No query tokens or credentials are accepted or emitted. Cache hashes establish integrity, not authenticity or immutable filesystem permissions; external edits are detected on reuse. Existing cache files are never overwritten by the collector.

`validate_source_cache(records, cache_dir: Path | None) -> list[dict]` is a read-only integrity boundary for collector records. It copies records, rejects cache path escapes/symlinks, verifies content-addressed raw SHA against bytes read once, and checks the `/index` response pointer against the canonical individual payload SHA and supplied payload. Pass the explicitly configured cache directory; `None` marks collector records `raw_cache_unavailable`. Other failures mark `raw_cache_integrity_error`. `suggest_identity` rejects records marked with `integrity_error`. Records without a raw-cache reference remain explicit standalone evidence and still require canonical payload integrity/provenance checks. OpenFIGI does not echo query WKN; query association is collector request-order provenance, not independent authenticity proof. The collector CLI returns status 0 on success and 2 on errors, with a sanitized diagnostic excluding request URLs or credentials.
