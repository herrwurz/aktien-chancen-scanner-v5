# Provider Credit Monitor Design

## Intent

Show the operator how much provider allowance remains while preserving the scanner's separate EUR 5 monthly safety limit.

## Design

- Read Tavily's current plan and credit usage from the authenticated official `GET /usage` endpoint and cache the result briefly.
- Never expose the Tavily key or raw provider error bodies.
- Estimate OpenAI consumption locally from provider-reported input and output tokens and label it as an estimate. A normal OpenAI project key cannot expose the prepaid/free balance, so the UI links to the provider billing dashboard instead of inventing a balance.
- Continue showing the scanner's pessimistic EUR reservations as the blocking internal control.
- Provider availability failures degrade to an explicit unavailable state and never prevent teaser analysis.

## Alternatives considered

- An OpenAI Admin API key could expose organization usage, but placing an organization-wide credential in this application would increase privileges and still would not provide a dependable free-credit balance. Rejected.
- Manually configured starting balances would become stale and could look authoritative. Rejected.

## Constraints

No new paid service, no secret values in responses, no automated recharge, and no provider balance may be presented as exact unless returned by the provider.
