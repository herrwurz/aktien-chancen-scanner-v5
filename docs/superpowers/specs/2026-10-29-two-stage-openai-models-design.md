# Two-stage OpenAI models

## Intent

Use a stronger model where reasoning quality changes candidate discovery, while retaining the
lower-cost model for repeated citation extraction. Keep deterministic evidence scoring and all
existing budget, provenance and historical-blind safeguards.

## Chosen approach

`gpt-4.1-mini-2025-04-14` remains the extraction default. `gpt-4.1-2025-04-14` becomes the
reasoning default for one teaser plan and one advisory final review. Both names are configurable
through Coolify. The final review may describe a preferred candidate and missing evidence but
must not silently reorder candidates or turn a hypothesis into an identification.

Alternatives considered were switching every request to the full model, which spends more on
repetitive extraction, and using only the full model for planning, which gives no final
cross-candidate check. The two-stage design buys both broader discovery and a final critique with
bounded calls.

## Accounting and output

Every audit entry already stores the request model and provider usage. Monthly usage is grouped
by model using explicit tariff entries for the two supported defaults. Unknown model tariffs are
reported as unknown rather than guessed. The runtime page and each analysis show model roles,
token counts when returned by OpenAI, and estimated provider cost. The existing monthly cap and
disabled auto-recharge remain unchanged.

## Safety and failure behavior

Invalid model names fail configuration validation. If the reasoning call fails, source extraction
and deterministic ranking continue with a visible diagnostic. Historical blind analysis makes no
live model calls. Model output remains advisory and cannot create primary evidence.
