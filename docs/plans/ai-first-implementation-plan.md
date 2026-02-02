# Plano: Evolução AI-First do KeryxFlow

## Objetivo
Transformar o KeryxFlow de "AI valida" para "AI opera" - Claude passa de validador (40% peso) para operador autônomo dentro de guardrails imutáveis.

---

## Fase 1: Guardrails Layer (Segurança Primeiro)
**Duração**: 1-2 semanas | **Prioridade**: CRÍTICA (resolve Issue #9)

### Arquivos a Criar
| Arquivo | Propósito |
|---------|-----------|
| `keryxflow/aegis/guardrails.py` | Limites imutáveis em código (frozen dataclass) |
| `keryxflow/aegis/portfolio.py` | Tracking de risco agregado do portfolio |
| `tests/test_aegis/test_guardrails.py` | Testes 100% coverage |

### Arquivos a Modificar
| Arquivo | Mudança |
|---------|---------|
| `keryxflow/aegis/risk.py` | Integrar GuardrailEnforcer antes de RiskManager |
| `keryxflow/config.py` | Validar que config não excede guardrails |

### Guardrails Propostos (Imutáveis)
```python
MAX_POSITION_SIZE_PCT = 10%      # Máx por posição
MAX_TOTAL_EXPOSURE_PCT = 50%     # Máx total exposto
MIN_CASH_RESERVE_PCT = 20%       # Sempre manter em caixa
MAX_LOSS_PER_TRADE_PCT = 2%      # Máx perda por trade
MAX_DAILY_LOSS_PCT = 5%          # Máx perda diária
CONSECUTIVE_LOSSES_HALT = 5      # Halt após 5 perdas
```

### Critérios de Sucesso
- [ ] Issue #9 resolvida: 3 posições a 2% cada = REJEITADO (6% > 5% daily limit)
- [ ] Guardrails não podem ser modificados em runtime
- [ ] 100% cobertura de testes em aegis/
- [ ] Backwards compatible com sistema atual

---

## Fase 2: Sistema de Memória
**Duração**: 2-3 semanas | **Dependência**: Fase 1 completa

### Novos Modelos de Dados (`core/models.py`)
```python
TradeEpisode     # Trade completo com reasoning e lessons_learned
TradingRule      # Regras aprendidas (source: learned/user/backtest)
MarketPattern    # Padrões identificados com estatísticas
```

### Novo Módulo: `keryxflow/memory/`
| Arquivo | Propósito |
|---------|-----------|
| `episodic.py` | Memória de trades (record/recall similar) |
| `semantic.py` | Regras e padrões (get_active_rules) |
| `manager.py` | Interface unificada (build_context_for_decision) |

### Integração
- `core/engine.py`: Gravar trades na memória após execução
- `oracle/brain.py`: Incluir contexto de memória no prompt do Claude

### Critérios de Sucesso
- [ ] Decisões de trade gravadas com contexto completo
- [ ] Outcomes gravados para aprendizado
- [ ] Contexto de memória incluído em prompts LLM
- [ ] Lookup de situações similares funcional

---

## Fase 3: Agent Tools
**Duração**: 2-3 semanas | **Dependência**: Fase 2 completa

### Novo Módulo: `keryxflow/agent/`
| Arquivo | Propósito |
|---------|-----------|
| `tools.py` | Framework de tools + TradingToolkit |
| `perception_tools.py` | get_price, get_ohlcv, get_order_book |
| `analysis_tools.py` | calculate_indicators, position_size |
| `execution_tools.py` | place_order, set_stop_loss (GUARDED) |
| `executor.py` | Execução segura com check de guardrails |

### Categorias de Tools
| Categoria | Tools | Guarded? |
|-----------|-------|----------|
| Perception | get_current_price, get_ohlcv, get_portfolio_state | Não |
| Analysis | calculate_indicators, calculate_position_size | Não |
| Introspection | recall_similar_trades, get_trading_rules | Não |
| Execution | place_order, close_position, set_stop_loss | **SIM** |

### Critérios de Sucesso
- [ ] 15+ tools implementadas e testadas
- [ ] Tools de execução passam por GuardrailEnforcer
- [ ] Formato compatível com Anthropic Tool Use API
- [ ] Error handling robusto

---

## Fase 4: Cognitive Agent
**Duração**: 3-4 semanas | **Dependência**: Fases 1-3 completas

### Novo Arquivo: `keryxflow/agent/cognitive.py`
```python
class CognitiveAgent:
    """Ciclo: Perceive → Remember → Analyze → Decide → Validate → Execute → Learn"""

    async def run_cycle(self) -> AgentCycleResult:
        context = await self._build_context()      # 1. Perceber
        decision = await self._get_decision(context)  # 2-4. Lembrar, Analisar, Decidir
        results = await self._execute_tools(decision)  # 5-6. Validar, Executar
        await self._update_memory(decision, results)   # 7. Aprender
```

### Modificação: `core/engine.py`
- Adicionar `agent_mode: bool` (default: False)
- Quando True: CognitiveAgent substitui SignalGenerator
- Quando False: comportamento atual preservado

### Fallback Behavior
- API Claude falha → volta para sinais técnicos
- Muitos erros → ativa circuit breaker
- Guardrails NUNCA podem ser bypassed

### Critérios de Sucesso
- [ ] Agent executa ciclos completos sem crashes
- [ ] Tool use loop funciona corretamente
- [ ] Fallback para modo técnico funcional
- [ ] Backwards compatible (agent_mode=False)

---

## Fase 5: Learning e Reflection
**Duração**: 2-3 semanas | **Dependência**: Fase 4 completa

### Novos Arquivos
| Arquivo | Propósito |
|---------|-----------|
| `agent/reflection.py` | Daily/weekly reflection, post-mortem de trades |
| `agent/strategy.py` | Seleção e adaptação de estratégias |
| `agent/scheduler.py` | Tarefas agendadas (daily close, weekly review) |

### Funcionalidades
- **Daily Reflection**: Analisa trades do dia, atualiza lessons_learned
- **Weekly Reflection**: Identifica padrões, cria/modifica regras
- **Trade Post-Mortem**: Claude revisa trade fechado e extrai lições

### Critérios de Sucesso
- [ ] Reflection diário roda e atualiza memória
- [ ] Regras criadas são significativas (review humano)
- [ ] Métricas de paper trading melhoram em 30 dias

---

## Arquivos Críticos

```
keryxflow/
├── aegis/
│   ├── guardrails.py    [CRIAR] Limites imutáveis
│   ├── portfolio.py     [CRIAR] Tracking agregado
│   └── risk.py          [MODIFICAR] Integrar guardrails
├── core/
│   ├── models.py        [MODIFICAR] +TradeEpisode, TradingRule, MarketPattern
│   ├── engine.py        [MODIFICAR] +agent_mode, +memory integration
│   └── database.py      [MODIFICAR] Registrar novos modelos
├── memory/              [CRIAR MÓDULO]
│   ├── episodic.py
│   ├── semantic.py
│   └── manager.py
├── agent/               [CRIAR MÓDULO]
│   ├── tools.py
│   ├── executor.py
│   ├── cognitive.py
│   ├── reflection.py
│   └── scheduler.py
├── oracle/
│   └── brain.py         [MODIFICAR] Aceitar memory context
└── config.py            [MODIFICAR] +AgentSettings, +guardrail validation
```

---

## Verificação

### Testes por Fase
- **Fase 1**: `pytest tests/test_aegis/test_guardrails.py` - 100% coverage
- **Fase 2**: `pytest tests/test_memory/` - memory persistence
- **Fase 3**: `pytest tests/test_agent/test_tools.py` - all tools work
- **Fase 4**: `pytest tests/integration/test_agent_cycle.py` - full cycle
- **Fase 5**: Paper trading 30 dias + review manual

### Validação de Segurança
```bash
# Testar cenário Issue #9
poetry run pytest tests/test_aegis/test_guardrails.py::test_aggregate_risk_rejection

# Testar guardrails imutáveis
poetry run pytest tests/test_aegis/test_guardrails.py::test_guardrails_immutable

# Integration test completo
poetry run pytest tests/integration/ -v
```

### Paper Trading Validation
Antes de cada fase ir para main:
1. 100+ paper trades
2. Verificar guardrails nunca bypassed
3. Checar memória grava/recupera corretamente
4. Validar decisões do agent são razoáveis

---

## Estimativas

| Fase | Duração | Esforço |
|------|---------|---------|
| 1. Guardrails | 1-2 semanas | Crítico - fazer primeiro |
| 2. Memory | 2-3 semanas | Fundação para AI-First |
| 3. Tools | 2-3 semanas | Interface do agent |
| 4. Agent | 3-4 semanas | Core da mudança |
| 5. Learning | 2-3 semanas | Melhoria contínua |
| **Total** | **10-15 semanas** | |

---

## Riscos e Mitigações

| Risco | Mitigação |
|-------|-----------|
| Claude toma decisão catastrófica | Guardrails imutáveis, checados antes de toda ação |
| Custo API Claude alto | Rate limiting, caching, agent_mode opcional |
| Performance degradada | Async everywhere, lazy loading |
| Memória cresce demais | Políticas de retenção, archive de dados antigos |
