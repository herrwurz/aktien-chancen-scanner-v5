# Historical Market Inputs V1.9 Design

## Intent

Replace constant HS5RMP volatility and FX assumptions with reproducible, point-in-time market
inputs while preserving the strict separation between observed warrant quotes, modeled warrant
values, and underlying signals.

## Design

An offline market-input layer reads normalized Tiingo current and prehistory files plus an ECB
USD-per-EUR CSV. For each trading session it computes 20/60/120-session annualized sample
volatility from adjusted-close log returns known through the preceding session. It also selects
the latest ECB fixing strictly before the session, so an opening/intraday simulation cannot see a
same-day fixing. Raw files remain external and are bound to the result by SHA-256.

The existing BSM engine receives the dated volatility and FX values. Each scenario identifies a
realized-volatility window and an explicitly hypothetical IV multiplier. Product ratio and
exercise style remain hypothetical. The report compares the modeled entry ask with EUR 0.17,
includes dated inputs and sensitivities, and never labels model output as observed performance.

A readiness audit validates file coverage, providers, corporate actions, publication timing,
product evidence, and availability of market inputs. Its batch interface evaluates readiness only;
it does not run 118 models with unverified product terms.

## Constraints and alternatives

The implementation extends the V1.8 engine instead of creating a second backtester. Using
same-day ECB rates was rejected because the daily bar includes times before the fixing. Using
fixed or forward-filled volatility was rejected because it can hide unavailable windows. Private
Hetzner inputs remain outside Git and are represented in tests by synthetic fixtures.
