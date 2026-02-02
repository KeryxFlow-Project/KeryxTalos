# Plan: AI-First Evolution of KeryxFlow

## Objective
Transform KeryxFlow from "AI validates" to "AI operates" - Claude evolves from validator (40% weight) to autonomous operator within immutable guardrails.

---

## Phase 1: Guardrails Layer (Safety First) ✅ COMPLETE
**Duration**: 1-2 weeks | **Priority**: CRITICAL (fixes Issue #9) | **Version**: v0.11.0

### Files to Create
| File | Purpose |
|------|---------|
| `keryxflow/aegis/guardrails.py` | Immutable limits in code (frozen dataclass) |
| `keryxflow/aegis/portfolio.py` | Aggregate portfolio risk tracking |
| `tests/test_aegis/test_guardrails.py` | Tests with 100% coverage |

### Files to Modify
| File | Change |
|------|--------|
| `keryxflow/aegis/risk.py` | Integrate GuardrailEnforcer before RiskManager |
| `keryxflow/config.py` | Validate that config does not exceed guardrails |

### Proposed Guardrails (Immutable)
```python
MAX_POSITION_SIZE_PCT = 10%      # Max per position
MAX_TOTAL_EXPOSURE_PCT = 50%     # Max total exposed
MIN_CASH_RESERVE_PCT = 20%       # Always keep in cash
MAX_LOSS_PER_TRADE_PCT = 2%      # Max loss per trade
MAX_DAILY_LOSS_PCT = 5%          # Max daily loss
CONSECUTIVE_LOSSES_HALT = 5      # Halt after 5 losses
```

### Success Criteria
- [x] Issue #9 fixed: 3 positions at 2% each = REJECTED (6% > 5% daily limit)
- [x] Guardrails cannot be modified at runtime
- [x] 100% test coverage on aegis/
- [x] Backwards compatible with current system

---

## Phase 2: Memory System ✅ COMPLETE
**Duration**: 2-3 weeks | **Dependency**: Phase 1 complete | **Version**: v0.12.0

### New Data Models (`core/models.py`)
```python
TradeEpisode     # Complete trade with reasoning and lessons_learned
TradingRule      # Learned rules (source: learned/user/backtest)
MarketPattern    # Identified patterns with statistics
```

### New Module: `keryxflow/memory/`
| File | Purpose |
|------|---------|
| `episodic.py` | Trade memory (record/recall similar) |
| `semantic.py` | Rules and patterns (get_active_rules) |
| `manager.py` | Unified interface (build_context_for_decision) |

### Integration
- `core/engine.py`: Record trades to memory after execution
- `oracle/brain.py`: Include memory context in prompt

### Success Criteria
- [x] Trade decisions recorded with full context
- [x] Outcomes recorded for learning
- [x] Memory context included in LLM prompts
- [x] Similar situation lookup functional

---

## Phase 3: Agent Tools ✅ COMPLETE
**Duration**: 2-3 weeks | **Dependency**: Phase 2 complete | **Version**: v0.13.0

### New Module: `keryxflow/agent/`
| File | Purpose |
|------|---------|
| `tools.py` | Tool framework + TradingToolkit |
| `perception_tools.py` | get_price, get_ohlcv, get_order_book |
| `analysis_tools.py` | calculate_indicators, position_size |
| `execution_tools.py` | place_order, set_stop_loss (GUARDED) |
| `executor.py` | Safe execution with guardrail checks |

### Tool Categories
| Category | Tools | Guarded? |
|----------|-------|----------|
| Perception | get_current_price, get_ohlcv, get_portfolio_state | No |
| Analysis | calculate_indicators, calculate_position_size | No |
| Introspection | recall_similar_trades, get_trading_rules | No |
| Execution | place_order, close_position, set_stop_loss | **YES** |

### Success Criteria
- [x] 15+ tools implemented and tested (20 tools total)
- [x] Execution tools pass through GuardrailEnforcer
- [x] Format compatible with Anthropic Tool Use API
- [x] Robust error handling

---

## Phase 4: Cognitive Agent
**Duration**: 3-4 weeks | **Dependency**: Phases 1-3 complete

### New File: `keryxflow/agent/cognitive.py`
```python
class CognitiveAgent:
    """Cycle: Perceive → Remember → Analyze → Decide → Validate → Execute → Learn"""

    async def run_cycle(self) -> AgentCycleResult:
        context = await self._build_context()         # 1. Perceive
        decision = await self._get_decision(context)  # 2-4. Remember, Analyze, Decide
        results = await self._execute_tools(decision) # 5-6. Validate, Execute
        await self._update_memory(decision, results)  # 7. Learn
```

### Modification: `core/engine.py`
- Add `agent_mode: bool` (default: False)
- When True: CognitiveAgent replaces SignalGenerator
- When False: current behavior preserved

### Fallback Behavior
- Claude API fails → fall back to technical signals
- Too many errors → activate circuit breaker
- Guardrails can NEVER be bypassed

### Success Criteria
- [ ] Agent executes complete cycles without crashes
- [ ] Tool use loop works correctly
- [ ] Fallback to technical mode functional
- [ ] Backwards compatible (agent_mode=False)

---

## Phase 5: Learning & Reflection
**Duration**: 2-3 weeks | **Dependency**: Phase 4 complete

### New Files
| File | Purpose |
|------|---------|
| `agent/reflection.py` | Daily/weekly reflection, trade post-mortems |
| `agent/strategy.py` | Strategy selection and adaptation |
| `agent/scheduler.py` | Scheduled tasks (daily close, weekly review) |

### Features
- **Daily Reflection**: Analyze day's trades, update lessons_learned
- **Weekly Reflection**: Identify patterns, create/modify rules
- **Trade Post-Mortem**: Claude reviews closed trade and extracts lessons

### Success Criteria
- [ ] Daily reflection runs and updates memory
- [ ] Created rules are meaningful (human review)
- [ ] Paper trading metrics improve over 30 days

---

## Critical Files

```
keryxflow/
├── aegis/
│   ├── guardrails.py    [CREATE] Immutable limits
│   ├── portfolio.py     [CREATE] Aggregate tracking
│   └── risk.py          [MODIFY] Integrate guardrails
├── core/
│   ├── models.py        [MODIFY] +TradeEpisode, TradingRule, MarketPattern
│   ├── engine.py        [MODIFY] +agent_mode, +memory integration
│   └── database.py      [MODIFY] Register new models
├── memory/              [CREATE MODULE]
│   ├── episodic.py
│   ├── semantic.py
│   └── manager.py
├── agent/               [CREATE MODULE]
│   ├── tools.py
│   ├── executor.py
│   ├── cognitive.py
│   ├── reflection.py
│   └── scheduler.py
├── oracle/
│   └── brain.py         [MODIFY] Accept memory context
└── config.py            [MODIFY] +AgentSettings, +guardrail validation
```

---

## Verification

### Tests per Phase
- **Phase 1**: `pytest tests/test_aegis/test_guardrails.py` - 100% coverage
- **Phase 2**: `pytest tests/test_memory/` - memory persistence
- **Phase 3**: `pytest tests/test_agent/test_tools.py` - all tools work
- **Phase 4**: `pytest tests/integration/test_agent_cycle.py` - full cycle
- **Phase 5**: Paper trading 30 days + manual review

### Security Validation
```bash
# Test Issue #9 scenario
pytest tests/test_aegis/test_guardrails.py::test_aggregate_risk_rejection

# Test immutable guardrails
pytest tests/test_aegis/test_guardrails.py::test_guardrails_immutable

# Full integration test
pytest tests/integration/ -v
```

### Paper Trading Validation
Before each phase goes to main:
1. 100+ paper trades
2. Verify guardrails never bypassed
3. Check memory records/retrieves correctly
4. Validate agent decisions are reasonable

---

## Estimates

| Phase | Duration | Effort |
|-------|----------|--------|
| 1. Guardrails | 1-2 weeks | Critical - do first |
| 2. Memory | 2-3 weeks | Foundation for AI-First |
| 3. Tools | 2-3 weeks | Agent interface |
| 4. Agent | 3-4 weeks | Core of the change |
| 5. Learning | 2-3 weeks | Continuous improvement |
| **Total** | **10-15 weeks** | |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Claude makes catastrophic decision | Immutable guardrails, checked before every action |
| High Claude API cost | Rate limiting, caching, agent_mode optional |
| Performance degradation | Async everywhere, lazy loading |
| Memory grows too large | Retention policies, archive old data |
