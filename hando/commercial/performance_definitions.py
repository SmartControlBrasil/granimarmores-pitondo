"""
Definições comerciais centralizadas para metas, score e desempenho.

Documentação complementar: docs/SALES_PERFORMANCE.md
"""
from decimal import Decimal

from commercial.lead_models import LeadStatus
from commercial.lead_models import LOSS_STATUSES
from quotes.models import QuoteStatus

# Lead recebido: criado dentro do período analisado (filtro created_at).

# Lead atendido: first_contact_at preenchido ou atividade de contato válida.
CONTACT_ACTIVITY_TYPES = {"call", "whatsapp", "email", "meeting", "site_visit"}

# Lead convertido: converted_customer preenchido.
# Lead ganho: status won. Lead perdido: status lost.

# Orçamento enviado: workflow real altera status para sent.
QUOTE_SENT_STATUSES = {QuoteStatus.SENT, QuoteStatus.VIEWED}

# Venda fechada: aceite do cliente (QuoteStatus.ACCEPTED).
# QuoteStatus.APPROVED é aprovação interna, não venda.
CLOSED_SALE_QUOTE_STATUS = QuoteStatus.ACCEPTED

# Valor potencial: pipeline aberto (leads não terminais + orçamentos enviados/visualizados).
OPEN_LEAD_STATUSES = [
    s for s, _ in LeadStatus.choices if s not in {LeadStatus.WON, *LOSS_STATUSES}
]
POTENTIAL_QUOTE_STATUSES = {
    QuoteStatus.SENT,
    QuoteStatus.VIEWED,
    QuoteStatus.APPROVED,
}

# Valor aprovado: somente orçamentos aceitos pelo cliente.
APPROVED_VALUE_QUOTE_STATUSES = {QuoteStatus.ACCEPTED}

# Taxa de conversão = ganhos / (ganhos + perdidos)
# Tempo de primeira resposta = first_contact_at - created_at
# Follow-up no prazo = tarefa concluída com completed_at <= due_at

# Limite para penalidade de lead sem primeiro contato (horas).
UNATTENDED_LEAD_HOURS = 48

# Projeção simples de meta: (realizado / dias decorridos) * dias totais
PROJECTION_METHOD = "linear_pace"

DEFAULT_POLICY_VALUES = {
    "name": "Política Comercial Padrão",
    "description": "Política inicial de pontuação comercial configurável.",
    "points_first_contact": 10,
    "points_quote_sent": 20,
    "points_follow_up_completed": 10,
    "points_lead_won": 50,
    "penalty_unattended_lead": 10,
    "penalty_overdue_follow_up": 5,
    "penalty_lost_without_reason": 10,
    "points_lead_created": 0,
    "points_lead_qualified": 5,
    "points_measurement_completed": 5,
    "points_quote_created": 0,
    "points_sales_value_factor": Decimal("0.00"),
    "maximum_daily_score": 0,
}

RANKING_METRICS = [
    ("score", "Score total"),
    ("approved_value", "Valor vendido"),
    ("conversion_rate", "Taxa de conversão"),
    ("response_time", "Velocidade de atendimento"),
    ("follow_up_compliance", "Follow-up no prazo"),
    ("won_leads", "Leads ganhos"),
    ("quotes_sent", "Orçamentos enviados"),
]

GOAL_SITUATIONS = {
    "achieved": "Atingida",
    "on_track": "No ritmo",
    "at_risk": "Em risco",
    "no_data": "Sem dados",
    "closed": "Encerrada",
}
