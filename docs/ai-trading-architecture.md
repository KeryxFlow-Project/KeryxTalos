# Arquitetura: Trading Bot Operado por IA

## Parte 1: Análise de Gaps

Esta seção identifica o que falta em projetos típicos de trading bots (como o KeryxTalos) para se tornarem sistemas verdadeiramente operados por IA.

---

### 1. Infraestrutura de Produção

#### 1.1 Monitoramento e Observabilidade
| Gap | Impacto | Solução |
|-----|---------|---------|
| Sem métricas em tempo real | Não sabe se sistema está saudável | Prometheus + Grafana |
| Logs não estruturados | Difícil debugar problemas | Logging JSON + ELK Stack |
| Sem alertas de saúde | Descobre problemas tarde | Alertmanager + PagerDuty |
| Sem rastreamento de latência | Não sabe onde está lento | OpenTelemetry tracing |

#### 1.2 Alta Disponibilidade
| Gap | Impacto | Solução |
|-----|---------|---------|
| Roda localmente | PC desliga = sistema para | Deploy em cloud (VPS/K8s) |
| Sem redundância | Single point of failure | Múltiplas instâncias + failover |
| Sem auto-recovery | Crash = intervenção manual | Supervisord / Kubernetes |
| Sem containerização | "Funciona na minha máquina" | Docker + Docker Compose |

#### 1.3 Gestão de Secrets
| Gap | Impacto | Solução |
|-----|---------|---------|
| API keys em .env | Risco de vazamento | HashiCorp Vault / AWS Secrets Manager |
| Sem rotação de keys | Comprometimento permanente | Rotação automática periódica |
| Secrets em repositório | Exposição pública | git-secrets + .gitignore rigoroso |

---

### 2. Robustez de Mercado

#### 2.1 Condições Extremas
| Gap | Impacto | Solução |
|-----|---------|---------|
| Sem tratamento de flash crash | Perdas catastróficas | Circuit breakers por volatilidade |
| Ignora gaps de preço | Stops não executam no preço | Ordens OCO + slippage tolerance |
| Sem modo de crise | Opera durante caos | Detector de regime + pause automático |

#### 2.2 Dependência de Exchange
| Gap | Impacto | Solução |
|-----|---------|---------|
| Apenas Binance | Se Binance cair, para tudo | Multi-exchange (Kraken, Coinbase, Bybit) |
| Sem fallback | Conta banida = game over | Contas em múltiplas exchanges |
| API rate limits | Throttling durante volatilidade | Queue de requests + backoff |

#### 2.3 Latência Competitiva
| Gap | Impacto | Solução |
|-----|---------|---------|
| Python puro | Lento vs bots institucionais | Aceitar limitação (swing trading) |
| Sem colocation | Latência de rede | VPS próximo aos servidores da exchange |
| Processamento síncrono | Bloqueios desnecessários | Asyncio + WebSockets |

---

### 3. Inteligência de Trading

#### 3.1 Estratégias
| Gap | Impacto | Solução |
|-----|---------|---------|
| Indicadores básicos (RSI, MACD) | Sem edge competitivo | ML para padrões não-óbvios |
| Sem análise de order flow | Perde informação crucial | Leitura de tape + footprint charts |
| Sem detecção de regime | Estratégia errada para contexto | Classificador de mercado (tendência/lateral/volátil) |

#### 3.2 Dados Alternativos
| Gap | Impacto | Solução |
|-----|---------|---------|
| Sem sentimento social | Perde sinais de Twitter/Reddit | APIs de sentimento (LunarCrush, Santiment) |
| Sem dados on-chain | Ignora movimentos de whales | Glassnode, Nansen, Arkham |
| Sem correlações macro | Ignora DXY, S&P500, treasuries | Feeds de dados macro |
| Sem funding rates | Ignora sinal de alavancagem | API de futuros perpétuos |

#### 3.3 IA Real vs Validação
| Gap | Impacto | Solução |
|-----|---------|---------|
| IA só valida, não decide | Autonomia limitada | Arquitetura agent-first |
| Sem memória entre sessões | Não aprende com erros | Sistema de memória persistente |
| Sem adaptação de estratégia | Estratégia fixa obsoleta | Meta-learning + auto-ajuste |

---

### 4. Gestão de Risco Avançada

#### 4.1 Proteções Ausentes
| Presente | Ausente | Solução |
|----------|---------|---------|
| Stop-loss fixo | Trailing stops dinâmicos | ATR-based trailing |
| Limite diário de perda | Value at Risk (VaR) em tempo real | Cálculo de VaR rolling |
| Max posições | Correlação entre posições | Matriz de correlação dinâmica |
| Circuit breaker simples | Stress testing automatizado | Simulação Monte Carlo |

#### 4.2 Portfolio-Level
| Gap | Impacto | Solução |
|-----|---------|---------|
| Posições tratadas isoladamente | Risco concentrado sem perceber | Cálculo de exposição agregada |
| Sem hedging | Sem proteção de downside | Posições inversamente correlacionadas |
| Sem rebalanceamento | Drift de alocação | Rebalanceamento periódico automático |

#### 4.3 Black Swan
| Gap | Impacto | Solução |
|-----|---------|---------|
| Sem contingência para eventos extremos | Colapso tipo FTX/Luna | Kill switch + capital em cold storage |
| Confiança excessiva em backtests | Overfitting histórico | Out-of-sample validation obrigatório |

---

### 5. Compliance e Regulatório

#### 5.1 Fiscal
| Gap | Impacto | Solução |
|-----|---------|---------|
| Sem registro de auditoria | Problemas com Receita Federal | Log imutável de todas operações |
| Sem relatórios fiscais | Declaração manual trabalhosa | Export automático formato RF |
| Sem cálculo de ganho de capital | Erro em declaração | Integração com Koinly/CoinTracker |

#### 5.2 Regulatório
| Gap | Impacto | Solução |
|-----|---------|---------|
| Ignora regulações locais | Risco legal | Consultoria jurídica + compliance check |
| Sem KYC/AML se escalar | Bloqueio de contas | Documentação de origem de fundos |

---

### 6. Testes e Validação

#### 6.1 Backtesting
| Gap | Impacto | Solução |
|-----|---------|---------|
| Look-ahead bias | Resultados irreais | Validação temporal estrita |
| Survivorship bias | Só testa moedas que existem hoje | Incluir delisted coins |
| Overfitting | Funciona no passado, falha no futuro | Walk-forward analysis |
| Sem custos realistas | Lucro ilusório | Incluir fees, spread, slippage |

#### 6.2 Validação Estatística
| Gap | Impacto | Solução |
|-----|---------|---------|
| Sem Monte Carlo | Não sabe distribuição de resultados | Simulações de 10k+ cenários |
| Sem stress testing | Não sabe comportamento em crise | Replay de 2020, 2022 |
| Métrica única (retorno) | Ignora risco | Sharpe, Sortino, Calmar, Max DD |

---

### 7. UX e Operacional

#### 7.1 Interface
| Gap | Impacto | Solução |
|-----|---------|---------|
| Apenas terminal | Difícil monitorar mobile | Dashboard web responsivo |
| Sem app mobile | Não acompanha fora do PC | PWA ou app nativo |
| Sem histórico visual | Difícil analisar performance | Gráficos de equity curve |

#### 7.2 Operações
| Gap | Impacto | Solução |
|-----|---------|---------|
| Single user | Não escala para equipe | Multi-tenant com permissões |
| Sem API própria | Não integra com outros sistemas | REST API documentada |
| Configuração manual | Erro humano | Interface de configuração validada |

---

### 8. Sustentabilidade do Projeto

#### 8.1 Comunidade
| Gap | Impacto | Solução |
|-----|---------|---------|
| 0 stars/forks | Sem validação externa | Marketing + documentação |
| Único contribuidor | Bus factor = 1 | Atrair contribuidores |
| Sem funding | Desenvolvimento para | GitHub Sponsors / modelo freemium |

#### 8.2 Documentação
| Gap | Impacto | Solução |
|-----|---------|---------|
| Sem API docs | Difícil estender | OpenAPI/Swagger |
| Sem arquitetura documentada | Difícil contribuir | ADRs (Architecture Decision Records) |
| Sem guia de contribuição real | PRs rejeitados/confusos | CONTRIBUTING.md detalhado |

---

### 9. O Gap Fundamental: IA que Valida vs IA que Opera

```
┌─────────────────────────────────────────────────────────────────┐
│                    ESTADO ATUAL (KeryxTalos)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Preços → Indicadores → REGRAS FIXAS → Sinal → Claude valida  │
│                              ↑                      ↓           │
│                         (decide)              (ok/não ok)       │
│                                                                 │
│   Claude é CONSULTOR, não OPERADOR                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    ESTADO NECESSÁRIO                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Dados → Claude PERCEBE → Claude ANALISA → Claude DECIDE      │
│              ↓                                    ↓              │
│         (ferramentas)                      (dentro de limites)  │
│              ↓                                    ↓              │
│   Claude EXECUTA → Claude AVALIA → Claude APRENDE              │
│                                          ↓                      │
│                                    (atualiza memória)           │
│                                                                 │
│   Claude é OPERADOR AUTÔNOMO com guardrails                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

| Aspecto | Valida (Atual) | Opera (Necessário) |
|---------|----------------|-------------------|
| Quem decide? | Código com regras fixas | Claude |
| Memória | Nenhuma | Episódica + Semântica + Procedural |
| Ferramentas | Claude não acessa | Claude usa diretamente |
| Adaptação | Manual | Automática baseada em resultados |
| Aprendizado | Não existe | Contínuo |

---

## Parte 2: Arquitetura Proposta

A arquitetura abaixo endereça os gaps identificados, com foco especial no gap fundamental de "IA que opera".

---

## Visão Geral

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           SISTEMA DE TRADING IA-FIRST                        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         CAMADA DE GOVERNANÇA                            │ │
│  │   Limites invioláveis em código • Não podem ser alterados pela IA       │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         AGENTE COGNITIVO (Claude)                       │ │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐            │ │
│  │  │ ESTRATEGO │  │  TÁTICO   │  │ EXECUTOR  │  │ AVALIADOR │            │ │
│  │  │ (longo    │→ │ (curto    │→ │ (ações    │→ │ (aprender │            │ │
│  │  │  prazo)   │  │  prazo)   │  │  agora)   │  │  com erros)│            │ │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘            │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐           │
│  │     MEMÓRIA      │  │   FERRAMENTAS    │  │    PERCEPÇÃO     │           │
│  │  ├─ Episódica    │  │  ├─ Exchange     │  │  ├─ Preços       │           │
│  │  ├─ Semântica    │  │  ├─ Análise      │  │  ├─ Order Book   │           │
│  │  └─ Procedural   │  │  ├─ Notícias     │  │  ├─ Notícias     │           │
│  │                  │  │  └─ On-chain     │  │  └─ Sentimento   │           │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘           │
│                                      │                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         INFRAESTRUTURA                                  │ │
│  │   Event Bus • Database • APIs • Monitoring • Logging                    │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Camada de Governança (Guardrails)

**Princípio:** A IA tem autonomia DENTRO de limites invioláveis definidos em código.

```python
# guardrails.py - NUNCA modificável pela IA

from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)  # Imutável
class TradingGuardrails:
    """Limites absolutos - código, não configuração"""
    
    # Limites de capital
    MAX_POSITION_SIZE_PCT: Decimal = Decimal("0.10")      # Máx 10% em uma posição
    MAX_TOTAL_EXPOSURE_PCT: Decimal = Decimal("0.50")     # Máx 50% exposto total
    MIN_RESERVE_PCT: Decimal = Decimal("0.20")            # Sempre manter 20% em caixa
    
    # Limites de perda
    MAX_LOSS_PER_TRADE_PCT: Decimal = Decimal("0.02")     # Máx 2% perda por trade
    MAX_DAILY_LOSS_PCT: Decimal = Decimal("0.05")         # Máx 5% perda diária
    MAX_WEEKLY_LOSS_PCT: Decimal = Decimal("0.10")        # Máx 10% perda semanal
    
    # Circuit breakers
    CONSECUTIVE_LOSSES_HALT: int = 5                       # Para após 5 perdas seguidas
    VOLATILITY_HALT_THRESHOLD: Decimal = Decimal("0.15")  # Para se volatilidade > 15%
    
    # Operacionais
    MAX_TRADES_PER_HOUR: int = 10
    MAX_TRADES_PER_DAY: int = 50
    ALLOWED_SYMBOLS: tuple = ("BTC/USDT", "ETH/USDT", "SOL/USDT")
    
    # Ações proibidas (whitelist approach)
    ALLOWED_ACTIONS: tuple = (
        "market_buy", "market_sell",
        "limit_buy", "limit_sell", 
        "cancel_order", "close_position",
        "set_stop_loss", "set_take_profit",
        "do_nothing"
    )


class GuardrailEnforcer:
    """Valida TODAS as ações antes de executar - não pode ser bypassed"""
    
    def __init__(self, guardrails: TradingGuardrails):
        self.g = guardrails
        
    def validate_action(self, action: dict, portfolio: dict) -> tuple[bool, str]:
        """Retorna (permitido, motivo)"""
        
        # Ação existe?
        if action["type"] not in self.g.ALLOWED_ACTIONS:
            return False, f"Ação '{action['type']}' não permitida"
        
        # Símbolo permitido?
        if action.get("symbol") and action["symbol"] not in self.g.ALLOWED_SYMBOLS:
            return False, f"Símbolo '{action['symbol']}' não permitido"
        
        # Tamanho da posição
        if action["type"] in ("market_buy", "limit_buy"):
            position_value = action["quantity"] * action["price"]
            position_pct = Decimal(str(position_value)) / Decimal(str(portfolio["total_value"]))
            
            if position_pct > self.g.MAX_POSITION_SIZE_PCT:
                return False, f"Posição {position_pct:.1%} excede máximo {self.g.MAX_POSITION_SIZE_PCT:.1%}"
        
        # Exposição total
        new_exposure = portfolio["current_exposure"] + action.get("value", 0)
        exposure_pct = Decimal(str(new_exposure)) / Decimal(str(portfolio["total_value"]))
        
        if exposure_pct > self.g.MAX_TOTAL_EXPOSURE_PCT:
            return False, f"Exposição total {exposure_pct:.1%} excederia máximo"
        
        # Reserva mínima
        remaining_cash = portfolio["cash"] - action.get("value", 0)
        reserve_pct = Decimal(str(remaining_cash)) / Decimal(str(portfolio["total_value"]))
        
        if reserve_pct < self.g.MIN_RESERVE_PCT:
            return False, f"Reserva cairia para {reserve_pct:.1%}, mínimo é {self.g.MIN_RESERVE_PCT:.1%}"
        
        # Circuit breakers
        if portfolio["consecutive_losses"] >= self.g.CONSECUTIVE_LOSSES_HALT:
            return False, f"Circuit breaker: {portfolio['consecutive_losses']} perdas consecutivas"
        
        if portfolio["daily_loss_pct"] >= float(self.g.MAX_DAILY_LOSS_PCT):
            return False, f"Limite de perda diária atingido: {portfolio['daily_loss_pct']:.1%}"
        
        return True, "OK"
```

---

## 2. Sistema de Memória

**Problema:** Claude não lembra de conversas anteriores.
**Solução:** Memória externa persistente em 3 camadas.

```python
# memory.py

from datetime import datetime, timedelta
from typing import Optional
import json
from sqlmodel import SQLModel, Field, Session, select
from sentence_transformers import SentenceTransformer
import numpy as np

# ============================================================
# MEMÓRIA EPISÓDICA - Cada trade como episódio completo
# ============================================================

class TradeEpisode(SQLModel, table=True):
    """Um trade completo com todo o contexto"""
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime
    
    # Decisão
    symbol: str
    action: str  # buy/sell
    reasoning: str  # Por que a IA decidiu isso
    confidence: float
    
    # Contexto no momento da decisão
    market_context: str  # JSON com indicadores, notícias, etc
    portfolio_state: str  # JSON com estado do portfolio
    
    # Execução
    entry_price: float
    quantity: float
    
    # Resultado (preenchido depois)
    exit_price: Optional[float] = None
    exit_timestamp: Optional[datetime] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    
    # Avaliação pós-trade (preenchido pela IA depois)
    post_mortem: Optional[str] = None  # O que deu certo/errado
    lessons_learned: Optional[str] = None
    would_repeat: Optional[bool] = None


class EpisodicMemory:
    """Gerencia memória de trades"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def record_trade(self, episode: TradeEpisode):
        self.session.add(episode)
        self.session.commit()
    
    def get_similar_situations(self, current_context: dict, limit: int = 5) -> list[TradeEpisode]:
        """Busca trades em situações similares"""
        # Simplificado - em produção usar embeddings
        statement = select(TradeEpisode).where(
            TradeEpisode.symbol == current_context["symbol"]
        ).order_by(TradeEpisode.timestamp.desc()).limit(limit * 3)
        
        candidates = self.session.exec(statement).all()
        
        # Filtrar por similaridade de contexto
        # (implementação real usaria vector similarity)
        return candidates[:limit]
    
    def get_recent_performance(self, days: int = 30) -> dict:
        """Estatísticas recentes"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        statement = select(TradeEpisode).where(
            TradeEpisode.timestamp >= cutoff,
            TradeEpisode.pnl.isnot(None)
        )
        trades = self.session.exec(statement).all()
        
        if not trades:
            return {"trades": 0}
        
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl < 0]
        
        return {
            "trades": len(trades),
            "win_rate": len(wins) / len(trades),
            "avg_win": np.mean([t.pnl for t in wins]) if wins else 0,
            "avg_loss": np.mean([t.pnl for t in losses]) if losses else 0,
            "total_pnl": sum(t.pnl for t in trades),
            "best_trade": max(trades, key=lambda t: t.pnl),
            "worst_trade": min(trades, key=lambda t: t.pnl),
        }


# ============================================================
# MEMÓRIA SEMÂNTICA - Conhecimento estruturado
# ============================================================

class MarketPattern(SQLModel, table=True):
    """Padrões de mercado aprendidos"""
    id: Optional[int] = Field(default=None, primary_key=True)
    
    name: str  # Ex: "BTC halving rally"
    description: str
    conditions: str  # JSON com condições que definem o padrão
    expected_outcome: str
    confidence: float
    
    # Estatísticas
    times_identified: int = 0
    times_correct: int = 0
    avg_return_when_correct: float = 0
    
    last_seen: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TradingRule(SQLModel, table=True):
    """Regras aprendidas pela IA"""
    id: Optional[int] = Field(default=None, primary_key=True)
    
    rule: str  # Ex: "Não comprar BTC quando RSI > 80 e funding rate > 0.1%"
    rationale: str
    source: str  # "learned", "user_defined", "backtest"
    
    # Efetividade
    times_applied: int = 0
    times_helpful: int = 0
    
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SemanticMemory:
    """Gerencia conhecimento estruturado"""
    
    def __init__(self, session: Session):
        self.session = session
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
    
    def get_relevant_patterns(self, market_state: dict) -> list[MarketPattern]:
        """Busca padrões que podem estar se formando"""
        # Implementação com similarity search
        pass
    
    def get_active_rules(self) -> list[TradingRule]:
        """Retorna regras ativas"""
        statement = select(TradingRule).where(TradingRule.active == True)
        return self.session.exec(statement).all()
    
    def learn_new_pattern(self, pattern: MarketPattern):
        """Adiciona novo padrão identificado"""
        self.session.add(pattern)
        self.session.commit()


# ============================================================
# MEMÓRIA PROCEDURAL - Estratégias e seus resultados
# ============================================================

class Strategy(SQLModel, table=True):
    """Uma estratégia de trading"""
    id: Optional[int] = Field(default=None, primary_key=True)
    
    name: str
    description: str
    parameters: str  # JSON com parâmetros
    
    # Performance
    total_trades: int = 0
    win_rate: float = 0
    sharpe_ratio: Optional[float] = None
    max_drawdown: float = 0
    total_return: float = 0
    
    # Status
    active: bool = True
    confidence: float = 0.5
    
    # Condições de uso
    best_market_conditions: str  # JSON - quando funciona melhor
    worst_market_conditions: str  # JSON - quando evitar
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None


class ProceduralMemory:
    """Gerencia estratégias"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_best_strategy_for(self, market_conditions: dict) -> Optional[Strategy]:
        """Retorna melhor estratégia para condições atuais"""
        strategies = self.session.exec(
            select(Strategy).where(Strategy.active == True)
        ).all()
        
        # Ranking por adequação às condições + performance histórica
        # Implementação real seria mais sofisticada
        if strategies:
            return max(strategies, key=lambda s: s.sharpe_ratio or 0)
        return None
    
    def update_strategy_performance(self, strategy_id: int, trade_result: dict):
        """Atualiza estatísticas da estratégia após trade"""
        strategy = self.session.get(Strategy, strategy_id)
        if strategy:
            strategy.total_trades += 1
            # Atualizar win_rate, sharpe, etc
            self.session.commit()


# ============================================================
# MEMORY MANAGER - Interface unificada
# ============================================================

class MemoryManager:
    """Interface unificada para todos os tipos de memória"""
    
    def __init__(self, session: Session):
        self.episodic = EpisodicMemory(session)
        self.semantic = SemanticMemory(session)
        self.procedural = ProceduralMemory(session)
    
    def build_context_for_decision(self, current_state: dict) -> str:
        """
        Monta contexto relevante para a IA tomar decisão.
        Este texto vai no prompt do Claude.
        """
        
        # Trades similares passados
        similar_trades = self.episodic.get_similar_situations(current_state)
        
        # Performance recente
        recent_perf = self.episodic.get_recent_performance(days=7)
        
        # Padrões relevantes
        patterns = self.semantic.get_relevant_patterns(current_state)
        
        # Regras ativas
        rules = self.semantic.get_active_rules()
        
        # Melhor estratégia
        best_strategy = self.procedural.get_best_strategy_for(current_state)
        
        context = f"""
## Memória de Trading

### Performance Recente (7 dias)
- Trades: {recent_perf.get('trades', 0)}
- Win Rate: {recent_perf.get('win_rate', 0):.1%}
- PnL Total: ${recent_perf.get('total_pnl', 0):,.2f}

### Trades Similares Passados
{self._format_similar_trades(similar_trades)}

### Padrões de Mercado Identificados
{self._format_patterns(patterns)}

### Regras Ativas
{self._format_rules(rules)}

### Estratégia Recomendada
{self._format_strategy(best_strategy)}
"""
        return context
    
    def _format_similar_trades(self, trades: list[TradeEpisode]) -> str:
        if not trades:
            return "Nenhum trade similar encontrado."
        
        lines = []
        for t in trades[:3]:
            result = "✅" if t.pnl and t.pnl > 0 else "❌"
            lines.append(f"- {result} {t.timestamp.date()}: {t.action} {t.symbol} → {t.pnl_pct:+.1%}")
            if t.lessons_learned:
                lines.append(f"  Lição: {t.lessons_learned}")
        
        return "\n".join(lines)
    
    def _format_patterns(self, patterns: list[MarketPattern]) -> str:
        if not patterns:
            return "Nenhum padrão relevante identificado."
        
        lines = []
        for p in patterns:
            accuracy = p.times_correct / p.times_identified if p.times_identified > 0 else 0
            lines.append(f"- {p.name} (precisão: {accuracy:.0%}): {p.expected_outcome}")
        
        return "\n".join(lines)
    
    def _format_rules(self, rules: list[TradingRule]) -> str:
        if not rules:
            return "Nenhuma regra específica ativa."
        
        return "\n".join([f"- {r.rule}" for r in rules[:5]])
    
    def _format_strategy(self, strategy: Optional[Strategy]) -> str:
        if not strategy:
            return "Nenhuma estratégia específica recomendada."
        
        return f"{strategy.name}: {strategy.description} (Sharpe: {strategy.sharpe_ratio:.2f})"
```

---

## 3. Ferramentas do Agente

**Princípio:** Claude acessa dados e executa ações através de ferramentas bem definidas.

```python
# tools.py

from typing import Any, Callable
from dataclasses import dataclass
from enum import Enum
import ccxt
from anthropic import Anthropic

class ToolCategory(Enum):
    PERCEPTION = "perception"      # Ler dados
    ANALYSIS = "analysis"          # Processar dados
    EXECUTION = "execution"        # Agir no mercado
    INTROSPECTION = "introspection"  # Consultar memória


@dataclass
class Tool:
    name: str
    description: str
    category: ToolCategory
    parameters: dict
    function: Callable
    requires_confirmation: bool = False


class TradingTools:
    """Todas as ferramentas disponíveis para o agente"""
    
    def __init__(self, exchange: ccxt.Exchange, memory: 'MemoryManager'):
        self.exchange = exchange
        self.memory = memory
        self.tools = self._register_tools()
    
    def _register_tools(self) -> dict[str, Tool]:
        return {
            # ============ PERCEPÇÃO ============
            "get_current_price": Tool(
                name="get_current_price",
                description="Obtém preço atual de um símbolo",
                category=ToolCategory.PERCEPTION,
                parameters={
                    "symbol": {"type": "string", "description": "Par de trading, ex: BTC/USDT"}
                },
                function=self._get_current_price
            ),
            
            "get_ohlcv": Tool(
                name="get_ohlcv",
                description="Obtém candles históricos (Open, High, Low, Close, Volume)",
                category=ToolCategory.PERCEPTION,
                parameters={
                    "symbol": {"type": "string"},
                    "timeframe": {"type": "string", "description": "1m, 5m, 15m, 1h, 4h, 1d"},
                    "limit": {"type": "integer", "description": "Número de candles (max 500)"}
                },
                function=self._get_ohlcv
            ),
            
            "get_order_book": Tool(
                name="get_order_book",
                description="Obtém livro de ofertas com bids e asks",
                category=ToolCategory.PERCEPTION,
                parameters={
                    "symbol": {"type": "string"},
                    "limit": {"type": "integer", "description": "Profundidade (5, 10, 20)"}
                },
                function=self._get_order_book
            ),
            
            "get_recent_trades": Tool(
                name="get_recent_trades",
                description="Obtém trades recentes executados no mercado",
                category=ToolCategory.PERCEPTION,
                parameters={
                    "symbol": {"type": "string"},
                    "limit": {"type": "integer"}
                },
                function=self._get_recent_trades
            ),
            
            "get_funding_rate": Tool(
                name="get_funding_rate",
                description="Obtém funding rate atual (mercado de futuros)",
                category=ToolCategory.PERCEPTION,
                parameters={
                    "symbol": {"type": "string"}
                },
                function=self._get_funding_rate
            ),
            
            "get_news": Tool(
                name="get_news",
                description="Busca notícias recentes sobre criptomoedas",
                category=ToolCategory.PERCEPTION,
                parameters={
                    "query": {"type": "string", "description": "Termo de busca"},
                    "limit": {"type": "integer"}
                },
                function=self._get_news
            ),
            
            # ============ ANÁLISE ============
            "calculate_indicators": Tool(
                name="calculate_indicators",
                description="Calcula indicadores técnicos (RSI, MACD, Bollinger, etc)",
                category=ToolCategory.ANALYSIS,
                parameters={
                    "symbol": {"type": "string"},
                    "indicators": {"type": "array", "items": {"type": "string"}},
                    "timeframe": {"type": "string"}
                },
                function=self._calculate_indicators
            ),
            
            "analyze_order_flow": Tool(
                name="analyze_order_flow",
                description="Analisa pressão de compra/venda no order book",
                category=ToolCategory.ANALYSIS,
                parameters={
                    "symbol": {"type": "string"}
                },
                function=self._analyze_order_flow
            ),
            
            "calculate_position_size": Tool(
                name="calculate_position_size",
                description="Calcula tamanho ideal de posição dado risco desejado",
                category=ToolCategory.ANALYSIS,
                parameters={
                    "symbol": {"type": "string"},
                    "entry_price": {"type": "number"},
                    "stop_loss_price": {"type": "number"},
                    "risk_percent": {"type": "number", "description": "Risco como % do portfolio"}
                },
                function=self._calculate_position_size
            ),
            
            # ============ EXECUÇÃO ============
            "place_market_order": Tool(
                name="place_market_order",
                description="Coloca ordem a mercado (execução imediata)",
                category=ToolCategory.EXECUTION,
                parameters={
                    "symbol": {"type": "string"},
                    "side": {"type": "string", "enum": ["buy", "sell"]},
                    "quantity": {"type": "number"}
                },
                function=self._place_market_order,
                requires_confirmation=True
            ),
            
            "place_limit_order": Tool(
                name="place_limit_order",
                description="Coloca ordem limitada em preço específico",
                category=ToolCategory.EXECUTION,
                parameters={
                    "symbol": {"type": "string"},
                    "side": {"type": "string", "enum": ["buy", "sell"]},
                    "quantity": {"type": "number"},
                    "price": {"type": "number"}
                },
                function=self._place_limit_order,
                requires_confirmation=True
            ),
            
            "set_stop_loss": Tool(
                name="set_stop_loss",
                description="Define stop-loss para posição existente",
                category=ToolCategory.EXECUTION,
                parameters={
                    "symbol": {"type": "string"},
                    "stop_price": {"type": "number"}
                },
                function=self._set_stop_loss,
                requires_confirmation=True
            ),
            
            "close_position": Tool(
                name="close_position",
                description="Fecha posição aberta completamente",
                category=ToolCategory.EXECUTION,
                parameters={
                    "symbol": {"type": "string"}
                },
                function=self._close_position,
                requires_confirmation=True
            ),
            
            "cancel_order": Tool(
                name="cancel_order",
                description="Cancela ordem pendente",
                category=ToolCategory.EXECUTION,
                parameters={
                    "order_id": {"type": "string"}
                },
                function=self._cancel_order
            ),
            
            # ============ INTROSPECÇÃO ============
            "get_portfolio_state": Tool(
                name="get_portfolio_state",
                description="Obtém estado atual do portfolio (saldos, posições, PnL)",
                category=ToolCategory.INTROSPECTION,
                parameters={},
                function=self._get_portfolio_state
            ),
            
            "recall_similar_trades": Tool(
                name="recall_similar_trades",
                description="Busca trades passados em situações similares",
                category=ToolCategory.INTROSPECTION,
                parameters={
                    "symbol": {"type": "string"},
                    "market_condition": {"type": "string", "description": "Descrição da condição atual"}
                },
                function=self._recall_similar_trades
            ),
            
            "get_my_rules": Tool(
                name="get_my_rules",
                description="Lista regras de trading que aprendi/defini",
                category=ToolCategory.INTROSPECTION,
                parameters={},
                function=self._get_my_rules
            ),
            
            "record_lesson": Tool(
                name="record_lesson",
                description="Registra uma lição aprendida para lembrar no futuro",
                category=ToolCategory.INTROSPECTION,
                parameters={
                    "lesson": {"type": "string"},
                    "context": {"type": "string"}
                },
                function=self._record_lesson
            ),
        }
    
    # Implementações das ferramentas
    async def _get_current_price(self, symbol: str) -> dict:
        ticker = await self.exchange.fetch_ticker(symbol)
        return {
            "symbol": symbol,
            "price": ticker["last"],
            "bid": ticker["bid"],
            "ask": ticker["ask"],
            "volume_24h": ticker["quoteVolume"],
            "change_24h": ticker["percentage"]
        }
    
    async def _get_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> list:
        ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=min(limit, 500))
        return [
            {
                "timestamp": candle[0],
                "open": candle[1],
                "high": candle[2],
                "low": candle[3],
                "close": candle[4],
                "volume": candle[5]
            }
            for candle in ohlcv
        ]
    
    async def _get_order_book(self, symbol: str, limit: int = 10) -> dict:
        book = await self.exchange.fetch_order_book(symbol, limit)
        return {
            "bids": book["bids"][:limit],  # [[price, quantity], ...]
            "asks": book["asks"][:limit],
            "spread": book["asks"][0][0] - book["bids"][0][0] if book["asks"] and book["bids"] else None
        }
    
    async def _calculate_indicators(self, symbol: str, indicators: list, timeframe: str) -> dict:
        import pandas as pd
        import pandas_ta as ta
        
        ohlcv = await self._get_ohlcv(symbol, timeframe, limit=200)
        df = pd.DataFrame(ohlcv)
        
        results = {}
        
        if "rsi" in indicators:
            results["rsi"] = float(df.ta.rsi().iloc[-1])
        
        if "macd" in indicators:
            macd = df.ta.macd()
            results["macd"] = {
                "macd": float(macd["MACD_12_26_9"].iloc[-1]),
                "signal": float(macd["MACDs_12_26_9"].iloc[-1]),
                "histogram": float(macd["MACDh_12_26_9"].iloc[-1])
            }
        
        if "bollinger" in indicators:
            bb = df.ta.bbands()
            results["bollinger"] = {
                "upper": float(bb["BBU_5_2.0"].iloc[-1]),
                "middle": float(bb["BBM_5_2.0"].iloc[-1]),
                "lower": float(bb["BBL_5_2.0"].iloc[-1])
            }
        
        if "atr" in indicators:
            results["atr"] = float(df.ta.atr().iloc[-1])
        
        return results
    
    async def _place_market_order(self, symbol: str, side: str, quantity: float) -> dict:
        order = await self.exchange.create_market_order(symbol, side, quantity)
        return {
            "order_id": order["id"],
            "status": order["status"],
            "filled": order["filled"],
            "average_price": order["average"],
            "cost": order["cost"]
        }
    
    async def _get_portfolio_state(self) -> dict:
        balance = await self.exchange.fetch_balance()
        positions = await self.exchange.fetch_positions() if hasattr(self.exchange, 'fetch_positions') else []
        
        return {
            "total_value": balance["total"].get("USDT", 0),
            "cash": balance["free"].get("USDT", 0),
            "positions": [
                {
                    "symbol": p["symbol"],
                    "side": p["side"],
                    "size": p["contracts"],
                    "entry_price": p["entryPrice"],
                    "unrealized_pnl": p["unrealizedPnl"]
                }
                for p in positions if p["contracts"] > 0
            ]
        }
    
    async def _recall_similar_trades(self, symbol: str, market_condition: str) -> list:
        trades = self.memory.episodic.get_similar_situations({
            "symbol": symbol,
            "condition": market_condition
        })
        return [
            {
                "date": t.timestamp.isoformat(),
                "action": t.action,
                "result": "win" if t.pnl and t.pnl > 0 else "loss",
                "pnl_pct": t.pnl_pct,
                "reasoning": t.reasoning,
                "lesson": t.lessons_learned
            }
            for t in trades
        ]
    
    # ... outras implementações ...
    
    def to_anthropic_tools(self) -> list[dict]:
        """Converte para formato de tools da API do Claude"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": {
                    "type": "object",
                    "properties": tool.parameters,
                    "required": list(tool.parameters.keys())
                }
            }
            for tool in self.tools.values()
        ]
```

---

## 4. Agente Cognitivo

**O cérebro do sistema:** Claude com personalidade, memória e ferramentas.

```python
# agent.py

from anthropic import Anthropic
from datetime import datetime
import json
from typing import Optional

class TradingAgent:
    """
    Agente de trading autônomo baseado em Claude.
    
    Ciclo: Perceber → Analisar → Decidir → Executar → Avaliar
    """
    
    SYSTEM_PROMPT = """
Você é um trader profissional autônomo operando no mercado de criptomoedas.

## Sua Identidade
- Nome: Atlas
- Objetivo: Acumular Bitcoin de forma consistente com gestão de risco rigorosa
- Estilo: Disciplinado, paciente, baseado em dados

## Princípios Fundamentais

1. **Preservação de Capital**
   - Nunca arrisque mais do que o permitido pelos guardrails
   - Quando em dúvida, não faça nada
   - Perdas pequenas são aceitáveis, perdas grandes são inaceitáveis

2. **Decisões Baseadas em Evidências**
   - Use dados, não opiniões
   - Considere múltiplos timeframes
   - Valide com indicadores independentes

3. **Aprendizado Contínuo**
   - Cada trade é uma lição
   - Registre seus erros para não repeti-los
   - Atualize suas regras com base em resultados

4. **Humildade**
   - O mercado está sempre certo
   - Você não pode prever o futuro
   - Admita quando não sabe

## Processo de Decisão

Antes de cada ação, siga este checklist:
1. Qual é o contexto macro do mercado?
2. O que os indicadores técnicos dizem?
3. Há notícias relevantes que podem impactar?
4. Já estive em situação similar? O que aconteceu?
5. Qual o risco/retorno desta operação?
6. Os guardrails permitem esta ação?
7. Se der errado, qual o plano de saída?

## Quando NÃO Operar

- Volatilidade extrema sem direção clara
- Notícias importantes pendentes (FOMC, CPI, etc)
- Após sequência de perdas (respeite o circuit breaker)
- Quando não entender o que está acontecendo
- "Fear of missing out" não é razão válida

## Formato de Resposta

Ao tomar uma decisão, sempre estruture assim:

### Análise
[Sua análise do momento atual]

### Decisão
[O que decidiu fazer e por quê]

### Ação
[A ferramenta que vai usar]

### Plano de Contingência
[O que fazer se der errado]
"""

    def __init__(
        self,
        anthropic_client: Anthropic,
        tools: 'TradingTools',
        memory: 'MemoryManager',
        guardrails: 'GuardrailEnforcer'
    ):
        self.client = anthropic_client
        self.tools = tools
        self.memory = memory
        self.guardrails = guardrails
        self.conversation_history = []
    
    async def run_cycle(self) -> dict:
        """
        Executa um ciclo completo de trading.
        Chamado periodicamente (ex: a cada 1 minuto).
        """
        
        # 1. Construir contexto
        context = await self._build_context()
        
        # 2. Pedir decisão ao Claude
        decision = await self._get_decision(context)
        
        # 3. Executar ações (com validação de guardrails)
        results = await self._execute_actions(decision)
        
        # 4. Avaliar e aprender
        await self._evaluate_and_learn(decision, results)
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "decision": decision,
            "results": results
        }
    
    async def _build_context(self) -> str:
        """Monta todo o contexto para decisão"""
        
        # Portfolio atual
        portfolio = await self.tools.tools["get_portfolio_state"].function()
        
        # Preços atuais
        prices = {}
        for symbol in ["BTC/USDT", "ETH/USDT"]:
            prices[symbol] = await self.tools.tools["get_current_price"].function(symbol)
        
        # Memória relevante
        memory_context = self.memory.build_context_for_decision({
            "symbol": "BTC/USDT",
            "prices": prices
        })
        
        # Estado dos guardrails
        guardrail_status = self._get_guardrail_status(portfolio)
        
        context = f"""
# Estado Atual: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

## Portfolio
- Valor Total: ${portfolio['total_value']:,.2f}
- Cash Disponível: ${portfolio['cash']:,.2f}
- Posições Abertas: {len(portfolio['positions'])}

## Preços Atuais
{self._format_prices(prices)}

## Guardrails
{guardrail_status}

{memory_context}

---

O que você quer fazer agora? Use as ferramentas disponíveis para:
1. Obter mais dados se necessário
2. Analisar o mercado
3. Tomar uma decisão de trading (ou decidir não fazer nada)
"""
        return context
    
    async def _get_decision(self, context: str) -> dict:
        """Obtém decisão do Claude com tool use"""
        
        messages = [{"role": "user", "content": context}]
        
        # Loop de tool use
        while True:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=self.SYSTEM_PROMPT,
                tools=self.tools.to_anthropic_tools(),
                messages=messages
            )
            
            # Processar resposta
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})
            
            # Verificar se há tool calls
            tool_calls = [block for block in assistant_content if block.type == "tool_use"]
            
            if not tool_calls:
                # Claude terminou de usar ferramentas
                break
            
            # Executar cada tool call
            tool_results = []
            for tool_call in tool_calls:
                tool_name = tool_call.name
                tool_input = tool_call.input
                
                # Executar ferramenta
                tool = self.tools.tools.get(tool_name)
                if tool:
                    try:
                        result = await tool.function(**tool_input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": json.dumps(result, default=str)
                        })
                    except Exception as e:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": f"Erro: {str(e)}",
                            "is_error": True
                        })
            
            messages.append({"role": "user", "content": tool_results})
        
        # Extrair decisão final do texto
        final_text = next(
            (block.text for block in assistant_content if hasattr(block, 'text')),
            ""
        )
        
        return {
            "reasoning": final_text,
            "tool_calls": [
                {"name": tc.name, "input": tc.input}
                for tc in tool_calls
            ] if tool_calls else [],
            "raw_response": response
        }
    
    async def _execute_actions(self, decision: dict) -> list[dict]:
        """Executa ações decididas, validando contra guardrails"""
        
        results = []
        
        for tool_call in decision.get("tool_calls", []):
            tool = self.tools.tools.get(tool_call["name"])
            
            if not tool:
                continue
            
            # Se é ação de execução, validar guardrails
            if tool.category == ToolCategory.EXECUTION:
                portfolio = await self.tools.tools["get_portfolio_state"].function()
                
                action = {
                    "type": tool_call["name"],
                    **tool_call["input"]
                }
                
                allowed, reason = self.guardrails.validate_action(action, portfolio)
                
                if not allowed:
                    results.append({
                        "tool": tool_call["name"],
                        "status": "blocked",
                        "reason": reason
                    })
                    continue
            
            # Executar
            try:
                result = await tool.function(**tool_call["input"])
                results.append({
                    "tool": tool_call["name"],
                    "status": "success",
                    "result": result
                })
            except Exception as e:
                results.append({
                    "tool": tool_call["name"],
                    "status": "error",
                    "error": str(e)
                })
        
        return results
    
    async def _evaluate_and_learn(self, decision: dict, results: list[dict]):
        """Avalia resultados e atualiza memória"""
        
        # Se houve trade, registrar na memória episódica
        execution_results = [r for r in results if r["status"] == "success" and "order" in r.get("tool", "")]
        
        for result in execution_results:
            episode = TradeEpisode(
                timestamp=datetime.utcnow(),
                symbol=result["result"].get("symbol", ""),
                action=result["tool"],
                reasoning=decision["reasoning"],
                confidence=0.7,  # Poderia ser extraído do raciocínio
                market_context=json.dumps({}),  # Contexto atual
                portfolio_state=json.dumps({}),  # Estado do portfolio
                entry_price=result["result"].get("average_price", 0),
                quantity=result["result"].get("filled", 0)
            )
            self.memory.episodic.record_trade(episode)
        
        # Se houve erro ou bloqueio, registrar lição
        blocked = [r for r in results if r["status"] == "blocked"]
        for block in blocked:
            await self.tools.tools["record_lesson"].function(
                lesson=f"Ação bloqueada: {block['reason']}",
                context=decision["reasoning"][:200]
            )
    
    def _format_prices(self, prices: dict) -> str:
        lines = []
        for symbol, data in prices.items():
            lines.append(f"- {symbol}: ${data['price']:,.2f} ({data['change_24h']:+.1f}% 24h)")
        return "\n".join(lines)
    
    def _get_guardrail_status(self, portfolio: dict) -> str:
        return f"""
- Posições permitidas: {len(portfolio.get('positions', []))}/3
- Exposição atual: {portfolio.get('current_exposure', 0) / portfolio.get('total_value', 1):.1%} de 50% máx
- Perdas hoje: {portfolio.get('daily_loss_pct', 0):.1%} de 5% máx
- Circuit breaker: {'🔴 ATIVO' if portfolio.get('circuit_breaker_active') else '🟢 OK'}
"""
```

---

## 5. Motor de Execução

**Orquestra ciclos do agente e gerencia infraestrutura.**

```python
# engine.py

import asyncio
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class TradingEngine:
    """
    Motor principal que orquestra o agente de trading.
    
    Responsabilidades:
    - Executar ciclos do agente em intervalos regulares
    - Gerenciar estado do sistema
    - Monitorar saúde e performance
    - Implementar circuit breakers de sistema
    """
    
    def __init__(
        self,
        agent: 'TradingAgent',
        config: dict
    ):
        self.agent = agent
        self.config = config
        
        self.running = False
        self.paused = False
        
        # Estatísticas
        self.stats = {
            "cycles_completed": 0,
            "trades_executed": 0,
            "errors": 0,
            "start_time": None,
            "last_cycle_time": None
        }
        
        # Circuit breakers de sistema
        self.system_circuit_breaker = {
            "consecutive_errors": 0,
            "max_errors": 5,
            "cooldown_until": None
        }
    
    async def start(self):
        """Inicia o motor de trading"""
        
        logger.info("Iniciando TradingEngine...")
        
        self.running = True
        self.stats["start_time"] = datetime.utcnow()
        
        # Validações iniciais
        await self._validate_system()
        
        # Loop principal
        while self.running:
            try:
                await self._run_cycle()
            except KeyboardInterrupt:
                logger.info("Interrupção manual detectada")
                break
            except Exception as e:
                logger.error(f"Erro no ciclo: {e}")
                await self._handle_error(e)
            
            # Aguardar próximo ciclo
            await asyncio.sleep(self.config.get("cycle_interval_seconds", 60))
        
        await self.stop()
    
    async def stop(self):
        """Para o motor graciosamente"""
        
        logger.info("Parando TradingEngine...")
        self.running = False
        
        # Fechar posições se configurado
        if self.config.get("close_positions_on_stop", False):
            await self._close_all_positions()
        
        # Salvar estado
        await self._save_state()
        
        logger.info("TradingEngine parado")
    
    async def pause(self):
        """Pausa trading (mantém monitoramento)"""
        self.paused = True
        logger.info("Trading pausado")
    
    async def resume(self):
        """Retoma trading"""
        self.paused = False
        logger.info("Trading retomado")
    
    async def _run_cycle(self):
        """Executa um ciclo completo"""
        
        # Verificar circuit breaker
        if self._is_circuit_breaker_active():
            logger.warning("Circuit breaker ativo, pulando ciclo")
            return
        
        # Verificar se está pausado
        if self.paused:
            logger.debug("Sistema pausado, apenas monitorando")
            await self._monitor_only()
            return
        
        cycle_start = datetime.utcnow()
        
        # Executar ciclo do agente
        result = await self.agent.run_cycle()
        
        # Atualizar estatísticas
        self.stats["cycles_completed"] += 1
        self.stats["last_cycle_time"] = datetime.utcnow()
        
        # Contar trades executados
        trades = [r for r in result.get("results", []) 
                  if r["status"] == "success" and "order" in r.get("tool", "")]
        self.stats["trades_executed"] += len(trades)
        
        # Reset contador de erros se ciclo foi bem-sucedido
        self.system_circuit_breaker["consecutive_errors"] = 0
        
        # Log resumo
        cycle_duration = (datetime.utcnow() - cycle_start).total_seconds()
        logger.info(
            f"Ciclo #{self.stats['cycles_completed']} completado em {cycle_duration:.1f}s | "
            f"Trades: {len(trades)}"
        )
    
    async def _validate_system(self):
        """Validações antes de iniciar"""
        
        # Verificar conexão com exchange
        try:
            await self.agent.tools.tools["get_current_price"].function("BTC/USDT")
        except Exception as e:
            raise RuntimeError(f"Falha na conexão com exchange: {e}")
        
        # Verificar saldo mínimo
        portfolio = await self.agent.tools.tools["get_portfolio_state"].function()
        if portfolio["total_value"] < self.config.get("minimum_balance", 100):
            raise RuntimeError(f"Saldo insuficiente: ${portfolio['total_value']}")
        
        logger.info("Validações do sistema OK")
    
    async def _handle_error(self, error: Exception):
        """Gerencia erros do sistema"""
        
        self.stats["errors"] += 1
        self.system_circuit_breaker["consecutive_errors"] += 1
        
        # Ativar circuit breaker se muitos erros
        if self.system_circuit_breaker["consecutive_errors"] >= self.system_circuit_breaker["max_errors"]:
            cooldown_minutes = self.config.get("error_cooldown_minutes", 30)
            self.system_circuit_breaker["cooldown_until"] = \
                datetime.utcnow() + timedelta(minutes=cooldown_minutes)
            
            logger.error(
                f"Circuit breaker ativado após {self.system_circuit_breaker['consecutive_errors']} erros. "
                f"Cooldown até {self.system_circuit_breaker['cooldown_until']}"
            )
            
            # Notificar
            await self._send_alert(
                "🚨 Circuit Breaker Ativado",
                f"Sistema pausado por {cooldown_minutes} minutos após múltiplos erros"
            )
    
    def _is_circuit_breaker_active(self) -> bool:
        """Verifica se circuit breaker está ativo"""
        
        if self.system_circuit_breaker["cooldown_until"]:
            if datetime.utcnow() < self.system_circuit_breaker["cooldown_until"]:
                return True
            else:
                # Cooldown expirou
                self.system_circuit_breaker["cooldown_until"] = None
                self.system_circuit_breaker["consecutive_errors"] = 0
                logger.info("Circuit breaker desativado, retomando operações")
        
        return False
    
    async def _monitor_only(self):
        """Modo somente monitoramento (sem trades)"""
        
        # Verificar posições existentes
        portfolio = await self.agent.tools.tools["get_portfolio_state"].function()
        
        # Verificar se algum stop foi atingido
        for position in portfolio.get("positions", []):
            # Lógica de monitoramento de stops
            pass
    
    async def _close_all_positions(self):
        """Fecha todas as posições abertas"""
        
        portfolio = await self.agent.tools.tools["get_portfolio_state"].function()
        
        for position in portfolio.get("positions", []):
            try:
                await self.agent.tools.tools["close_position"].function(
                    symbol=position["symbol"]
                )
                logger.info(f"Posição {position['symbol']} fechada")
            except Exception as e:
                logger.error(f"Erro ao fechar {position['symbol']}: {e}")
    
    async def _save_state(self):
        """Salva estado para recovery"""
        # Implementar persistência de estado
        pass
    
    async def _send_alert(self, title: str, message: str):
        """Envia alerta (Telegram, Discord, etc)"""
        # Implementar notificações
        pass


# ============================================================
# PONTO DE ENTRADA
# ============================================================

async def main():
    """Função principal"""
    
    from anthropic import Anthropic
    import ccxt.async_support as ccxt
    from sqlmodel import Session, create_engine
    
    # Configuração
    config = {
        "cycle_interval_seconds": 60,
        "minimum_balance": 100,
        "error_cooldown_minutes": 30,
        "close_positions_on_stop": True
    }
    
    # Inicializar componentes
    anthropic_client = Anthropic()
    
    exchange = ccxt.binance({
        'apiKey': 'YOUR_API_KEY',
        'secret': 'YOUR_SECRET',
        'sandbox': True  # Usar testnet primeiro!
    })
    
    engine_db = create_engine("sqlite:///trading.db")
    session = Session(engine_db)
    
    # Construir sistema
    memory = MemoryManager(session)
    guardrails = GuardrailEnforcer(TradingGuardrails())
    tools = TradingTools(exchange, memory)
    agent = TradingAgent(anthropic_client, tools, memory, guardrails)
    engine = TradingEngine(agent, config)
    
    # Executar
    try:
        await engine.start()
    finally:
        await exchange.close()
        session.close()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 6. Fluxo de Decisão Visual

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CICLO DE TRADING                                  │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │   TRIGGER    │  A cada 60 segundos
    │   (Timer)    │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐     ┌─────────────────────────────────────────────────┐
    │   PERCEBER   │────▶│  • Preços atuais (get_current_price)            │
    │              │     │  • Portfolio (get_portfolio_state)               │
    │              │     │  • Order book (get_order_book)                   │
    │              │     │  • Notícias (get_news)                           │
    └──────┬───────┘     └─────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────┐     ┌─────────────────────────────────────────────────┐
    │   LEMBRAR    │────▶│  • Trades similares passados                    │
    │   (Memória)  │     │  • Regras aprendidas                            │
    │              │     │  • Performance recente                           │
    │              │     │  • Padrões identificados                         │
    └──────┬───────┘     └─────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────┐     ┌─────────────────────────────────────────────────┐
    │   ANALISAR   │────▶│  • Indicadores técnicos (calculate_indicators)  │
    │   (Claude)   │     │  • Order flow (analyze_order_flow)              │
    │              │     │  • Cálculo de posição (calculate_position_size) │
    └──────┬───────┘     └─────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────┐     ┌─────────────────────────────────────────────────┐
    │   DECIDIR    │────▶│  Claude decide:                                 │
    │   (Claude)   │     │  • Comprar? Vender? Nada?                       │
    │              │     │  • Quanto? A que preço?                          │
    │              │     │  • Stop loss? Take profit?                       │
    └──────┬───────┘     └─────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────┐     ┌─────────────────────────────────────────────────┐
    │   VALIDAR    │────▶│  Guardrails verificam:                          │
    │  (Guardrails)│     │  • Tamanho da posição OK?                       │
    │              │     │  • Exposição total OK?                           │
    │              │     │  • Circuit breaker OK?                           │
    │              │     │  • Limite diário OK?                             │
    └──────┬───────┘     └─────────────────────────────────────────────────┘
           │
           ├─── NÃO ──▶ Bloqueia ação, registra motivo
           │
           ▼ SIM
    ┌──────────────┐     ┌─────────────────────────────────────────────────┐
    │   EXECUTAR   │────▶│  • Enviar ordem para exchange                   │
    │              │     │  • Definir stops                                 │
    │              │     │  • Aguardar confirmação                          │
    └──────┬───────┘     └─────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────┐     ┌─────────────────────────────────────────────────┐
    │   APRENDER   │────▶│  • Registrar trade na memória episódica         │
    │   (Memória)  │     │  • Atualizar estatísticas                       │
    │              │     │  • Registrar lições (se erro/bloqueio)          │
    └──────┬───────┘     └─────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────┐
    │   AGUARDAR   │  60 segundos até próximo ciclo
    │   PRÓXIMO    │
    │    CICLO     │
    └──────────────┘
```

---

## 7. Considerações de Produção

### Custos Estimados

| Componente | Custo Mensal |
|------------|--------------|
| Claude API (Sonnet, ~1M tokens/dia) | $90-150 |
| VPS (4GB RAM, 2 CPU) | $20-40 |
| Binance Fees (assumindo $10k volume) | $20-100 |
| Monitoring (Grafana Cloud) | $0-50 |
| **Total** | **$130-340/mês** |

### Latência

```
Ciclo típico:
├── Fetch dados (exchange)     200-500ms
├── Construir contexto          50-100ms
├── Claude pensa + tools     2,000-8,000ms  ← Gargalo
├── Validar guardrails           5-10ms
├── Executar ordem            100-500ms
└── Atualizar memória           50-100ms
                             ─────────────
                            ~3-10 segundos total
```

**Implicação:** Não serve para scalping. Adequado para swing trading (posições de horas/dias).

### Resiliência

```python
# Padrões essenciais para produção

# 1. Retry com backoff exponencial
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
async def safe_api_call():
    ...

# 2. Timeout em operações críticas
async with asyncio.timeout(30):
    await exchange.create_order(...)

# 3. Health checks
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "last_cycle": engine.stats["last_cycle_time"],
        "errors_last_hour": get_recent_errors()
    }

# 4. Graceful shutdown
signal.signal(signal.SIGTERM, lambda: asyncio.create_task(engine.stop()))
```

---

## 8. Roadmap de Implementação

### Fase 1: Fundação (2-3 semanas)
- [ ] Setup projeto Python com Poetry
- [ ] Implementar Guardrails
- [ ] Implementar Tools (percepção + análise)
- [ ] Integração básica com Binance (paper trading)

### Fase 2: Agente (2-3 semanas)
- [ ] Sistema de memória (SQLite + SQLModel)
- [ ] Agente com tool use do Claude
- [ ] Loop básico de trading

### Fase 3: Robustez (2-3 semanas)
- [ ] Engine com circuit breakers
- [ ] Logging estruturado
- [ ] Notificações (Telegram)
- [ ] Testes automatizados

### Fase 4: Produção (2-4 semanas)
- [ ] Deploy em cloud (Docker + VPS)
- [ ] Monitoring (Prometheus + Grafana)
- [ ] Backtesting para validação
- [ ] Paper trading extensivo

### Fase 5: Live (cauteloso)
- [ ] Live trading com capital mínimo
- [ ] Monitoramento 24/7 por 30 dias
- [ ] Ajustes baseados em resultados reais
- [ ] Escalar gradualmente

---

## Conclusão

Esta arquitetura transforma o conceito de "IA que valida" para "IA que opera":

| Aspecto | KeryxFlow Atual | Esta Arquitetura |
|---------|-----------------|------------------|
| Decisão | Regras fixas | Claude decide |
| Memória | Nenhuma | Episódica + Semântica + Procedural |
| Ferramentas | IA não acessa | IA usa diretamente |
| Aprendizado | Manual | Automático |
| Autonomia | Baixa | Alta (com guardrails) |

**Trade-offs:**
- ✅ Flexibilidade e adaptação
- ✅ Aprendizado com experiência
- ❌ Maior custo (API Claude)
- ❌ Maior latência
- ❌ Mais complexo de debugar

**Recomendação:** Implementar gradualmente, começando pelo sistema de memória e ferramentas, validando extensivamente em paper trading antes de qualquer capital real.

---

## Parte 3: Checklist de Gaps vs Soluções

### Mapeamento: O que esta arquitetura resolve

| # | Gap Identificado | Resolvido? | Onde na Arquitetura |
|---|------------------|------------|---------------------|
| **INFRAESTRUTURA** |
| 1.1 | Monitoramento e observabilidade | ⚠️ Parcial | Seção 7 menciona, não implementa |
| 1.2 | Alta disponibilidade | ⚠️ Parcial | Engine tem graceful shutdown |
| 1.3 | Gestão de secrets | ❌ Não | Usar Vault/AWS separadamente |
| **ROBUSTEZ DE MERCADO** |
| 2.1 | Condições extremas | ✅ Sim | Guardrails + circuit breakers |
| 2.2 | Multi-exchange | ❌ Não | Arquitetura suporta, não implementado |
| 2.3 | Latência | ⚠️ Aceito | Documentado como limitação (swing trading) |
| **INTELIGÊNCIA** |
| 3.1 | Estratégias avançadas | ⚠️ Parcial | Ferramentas de análise, ML não incluído |
| 3.2 | Dados alternativos | ⚠️ Parcial | Tool `get_news`, on-chain não incluído |
| 3.3 | IA que opera (não só valida) | ✅ Sim | Core da arquitetura (Agente + Memória) |
| **GESTÃO DE RISCO** |
| 4.1 | Proteções avançadas | ✅ Sim | Guardrails + position sizing |
| 4.2 | Portfolio-level risk | ⚠️ Parcial | Exposição total, correlação não |
| 4.3 | Black swan protection | ✅ Sim | Circuit breakers múltiplos |
| **COMPLIANCE** |
| 5.1 | Auditoria fiscal | ⚠️ Parcial | TradeEpisode tem dados, export não |
| 5.2 | Regulatório | ❌ Não | Fora do escopo técnico |
| **TESTES** |
| 6.1 | Backtesting robusto | ❌ Não | Não incluído nesta arquitetura |
| 6.2 | Validação estatística | ❌ Não | Não incluído nesta arquitetura |
| **UX** |
| 7.1 | Interface web/mobile | ❌ Não | Apenas código backend |
| 7.2 | Multi-user | ❌ Não | Single user |
| **SUSTENTABILIDADE** |
| 8.1 | Comunidade | N/A | Depende de execução |
| 8.2 | Documentação | ✅ Sim | Este documento |

---

### O que ainda precisa ser adicionado

#### Prioridade Alta (Crítico para Produção)
```
[ ] Monitoramento (Prometheus + Grafana)
[ ] Deploy containerizado (Docker + docker-compose)
[ ] Backup e recovery de estado
[ ] Multi-exchange fallback
[ ] Backtesting integrado
[ ] Relatórios fiscais (formato RF brasileira)
```

#### Prioridade Média (Importante para Escala)
```
[ ] Dashboard web
[ ] Notificações avançadas (Telegram com comandos)
[ ] Dados on-chain (Glassnode/Nansen API)
[ ] Correlação entre posições
[ ] Walk-forward validation
[ ] Rate limiting robusto
```

#### Prioridade Baixa (Nice to Have)
```
[ ] App mobile
[ ] Multi-tenant
[ ] Marketplace de estratégias
[ ] ML para detecção de regime
[ ] API pública documentada
```

---

### Estimativa de Esforço Total

| Fase | Escopo | Tempo | Custo Dev* |
|------|--------|-------|-----------|
| 1. Fundação | Setup + Guardrails + Tools básicos | 2-3 semanas | $3-5k |
| 2. Agente | Memória + Claude Agent + Loop | 2-3 semanas | $3-5k |
| 3. Robustez | Engine + Circuit breakers + Notificações | 2-3 semanas | $3-5k |
| 4. Produção | Docker + Monitoring + Testes | 2-4 semanas | $4-8k |
| 5. Validação | Paper trading extensivo | 4-8 semanas | $2-4k |
| 6. Extras | Dashboard + Fiscal + On-chain | 4-8 semanas | $6-12k |
| **Total** | | **16-32 semanas** | **$21-39k** |

*Estimativa para desenvolvedor Python sênior freelancer

---

### Métricas de Sucesso

Antes de ir para produção com capital real, validar:

| Métrica | Mínimo Aceitável | Ideal |
|---------|------------------|-------|
| Win Rate (paper) | > 50% | > 55% |
| Profit Factor | > 1.3 | > 1.8 |
| Sharpe Ratio | > 1.0 | > 1.5 |
| Max Drawdown | < 15% | < 10% |
| Trades em paper | > 100 | > 500 |
| Uptime do sistema | > 95% | > 99% |
| Latência média | < 10s | < 5s |
| Erros por dia | < 5 | < 1 |

---

## Apêndice: Decisões de Arquitetura (ADRs)

### ADR-001: Claude como Operador, não Validador
**Contexto:** Projetos existentes usam IA apenas para validar decisões de regras fixas.
**Decisão:** Claude será o tomador de decisão primário, com guardrails em código.
**Consequências:** Maior flexibilidade, maior custo de API, necessidade de guardrails robustos.

### ADR-002: Memória em 3 Camadas
**Contexto:** Claude não tem memória entre sessões.
**Decisão:** Implementar memória episódica (trades), semântica (padrões), procedural (estratégias).
**Consequências:** Aprendizado real, complexidade de implementação, necessidade de embeddings.

### ADR-003: Guardrails Invioláveis em Código
**Contexto:** IA autônoma pode tomar decisões catastróficas.
**Decisão:** Limites absolutos em código Python, não configuráveis pela IA.
**Consequências:** Segurança garantida, possível frustração quando IA quer agir mas não pode.

### ADR-004: Aceitar Limitação de Latência
**Contexto:** Chamadas ao Claude levam 2-10 segundos.
**Decisão:** Aceitar que sistema não serve para scalping, focar em swing trading.
**Consequências:** Mercado-alvo limitado, mas arquitetura mais simples.

### ADR-005: SQLite para MVP, PostgreSQL para Escala
**Contexto:** Necessidade de persistência de memória.
**Decisão:** Começar com SQLite (simples), migrar para PostgreSQL quando necessário.
**Consequências:** Desenvolvimento rápido inicial, migração futura planejada.

---

**Documento criado em:** Fevereiro 2026
**Versão:** 1.0
**Status:** Proposta de Arquitetura
