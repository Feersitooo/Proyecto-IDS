"""Política de circulación; no conoce HTTP ni un formato institucional futuro."""
from datetime import timedelta
from . import data
from .errors import DomainError
from .timeutils import now_utc, SANTIAGO


def eligible(user_id):
    user = data.user(user_id)
    if not user or user['role'] != 'alumno':
        raise DomainError('El solicitante debe ser un alumno.', 400)
    if not user['account_active'] or not user['lending_enabled']:
        raise DomainError('Cuenta no habilitada para préstamos. ' + (user['block_reason'] or 'Consulta con biblioteca.'))
    if data.has_overdue(user_id):
        raise DomainError('Hay material vencido pendiente de devolución. Regulariza la situación con biblioteca.')
    return user


def capacity(user_id, collection_id, exclude_request=0):
    user = eligible(user_id)
    policy = data.rule(user['user_type'], collection_id)
    if not policy:
        raise DomainError('No existe una regla de préstamo para este tipo de usuario y colección.')
    if data.commitments(user_id, collection_id, exclude_request) >= policy['max_items']:
        raise DomainError(f"Se alcanzó el límite de {policy['max_items']} ejemplares de esta colección, incluyendo asignaciones para retiro.")
    return policy


def suggested_due(user_id, collection_id):
    user = data.user(user_id)
    policy = data.rule(user['user_type'], collection_id)
    if not policy:
        return None
    # Decisión provisional: días calendario. El administrador confirma/ajusta.
    return (now_utc().astimezone(SANTIAGO) + timedelta(days=policy['loan_days'])).replace(hour=policy['due_hour'], minute=0, second=0, microsecond=0)
