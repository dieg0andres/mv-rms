"""Invented HN-F1 descriptions, not data, scientific findings or firm defaults."""


def hypothesis_fields():
    return {
        "title": "Invented next-session reversal after a large down day",
        "claim": "For the stated fictional signal, mean next-session open-to-close gross total return is proposed to exceed matched-window zero-yield cash.",
        "claim_basis": "gross_return",
        "economic_rationale": "Temporary selling pressure may depress prices; this is an invented proposition.",
        "expected_opportunity": "A following-session reversal may create opportunity; costs and capacity could remove it.",
        "persistence_argument": "Episodic liquidity needs may recur; competition could reduce the effect.",
        "competing_explanations": "Market rebound, risk exposure, fixture construction and unavailable entry prices may explain apparent results.",
        "falsification_condition": "A later valid preregistered test with no predicted advantage would undermine the claim. Insufficient observations or unavailable data remain inconclusive.",
        "market": "etfs", "universe": "Fixed invented members SYNTH-ETF-A, SYNTH-ETF-B, SYNTH-ETF-C, selected before the fictional window.",
        "direction": "long",
        "signal": "Prior session close-to-close total return at or below -2%; fixture description only.",
        "information_availability": "Observe after the fictional close, assuming five minutes of availability delay. No real data is used.",
        "decision_schedule": "Five minutes after each close in America/New_York. Invented SYNTH-NY calendar: 2026-01-05 and 2026-01-06, opens 09:30, closes 16:00. No real exchange-calendar claim.",
        "entry_conditions": "Enter at next fictional session open only if flat. Select the most negative qualifying return; break ties alphabetically. Repeated signals while invested do not add.",
        "execution_timing": "Intended next-session open entry after delayed observation; fills are undefined until a future Test Plan.",
        "exit_conditions": "Close at the entry session's close. No price stop or profit target.",
        "exit_precedence": "Scheduled exit and maximum holding both refer to that close; unknown within-bar ordering is unresolved.",
        "effect_horizon": {"kind": "fixed", "quantity": "1", "unit": "trading_sessions", "start_anchor": "Next fictional session open", "counting_convention": "That session counts as one", "calendar": "SYNTH-NY: 2026-01-05, 2026-01-06; 09:30-16:00 America/New_York"},
        "maximum_holding_period": {"kind": "fixed", "quantity": "1", "unit": "trading_sessions", "start_anchor": "Intended entry fill", "counting_convention": "Fill session counts as session one and ends at its close", "calendar": "SYNTH-NY: 2026-01-05, 2026-01-06; 09:30-16:00 America/New_York"},
        "sizing_method": "equity_fraction",
        "sizing_basis": "10% of pre-entry portfolio equity in fictional USD, measured before submission.",
        "sizing_rule": "Use a price available before submission and round down to whole units; no additional concurrent signals.",
        "exposure_limits": "At most one position, 10% intended gross exposure, no leverage or borrowing. Fill/exposure handling awaits a Test Plan.",
        "implementation_assumptions": "No final liquidity, spread, fee, slippage, settlement, execution or cost model exists.",
        "intended_benchmark_name": "Invented zero-yield USD cash",
        "intended_benchmark_definition": "Fictional zero-yield cash over matching open-to-close windows in USD, with no rebalancing.",
        "intended_benchmark_rationale": "Compares taking the proposed position with remaining in cash; does not control market beta.",
        "research_limitations": "Invented software fixture only: no qualified data, empirical results, Test Plan, execution model, statistical threshold or independent research verdict.",
    }
