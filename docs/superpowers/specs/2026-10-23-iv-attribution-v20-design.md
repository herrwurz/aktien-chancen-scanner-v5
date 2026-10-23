# IV Attribution V2.0 Design

V2.0 adds an opt-in research report beside the unchanged V1.9 report. For every existing market
scenario it evaluates three IV paths against identical underlying bars, FX, spread, rates,
dividend assumptions and trading rules: entry IV held constant, rolling realized volatility times
the declared IV multiplier, and a dated linear IV stress factor applied to entry IV.

Every modeled price change is decomposed against the entry state. Stock, time, IV and FX are
revalued one factor at a time; the residual is reported as interaction/order effect so components
sum exactly to the modeled fair-value change. This is a model attribution, not an observed warrant
price decomposition.

Close-based loss signals execute at the next session's modeled bid open. A parallel hold strategy
records the same signal but disables that exit and continues under the remaining target/stop rules.
Exit reports compare zero, baseline and explicit stress slippage. EUR 0.17 remains an external
recommendation indication and is never an optimization target.

V1.9 commands, output mode and regression tests remain intact. V2.0 requires a separate CLI
command and assumption file. Private Hetzner archives remain external and read-only.
