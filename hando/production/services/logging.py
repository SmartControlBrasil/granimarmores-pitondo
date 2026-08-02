from production.models import ProductionLog


def add_production_log(
    *,
    production_order,
    log_type,
    description,
    actor=None,
    piece=None,
    piece_stage=None,
    started_at=None,
    ended_at=None,
    duration_minutes=None,
    quantity_processed=None,
    quantity_rejected=None,
):
    return ProductionLog.objects.create(
        production_order=production_order,
        piece=piece,
        piece_stage=piece_stage,
        log_type=log_type,
        description=description,
        started_at=started_at,
        ended_at=ended_at,
        duration_minutes=duration_minutes,
        quantity_processed=quantity_processed,
        quantity_rejected=quantity_rejected,
        created_by=actor,
    )
