"""UTC en persistencia; America/Santiago en formularios y presentación."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from flask import current_app

SANTIAGO = ZoneInfo('America/Santiago')
UTC = timezone.utc


def now_utc():
    clock = current_app.config.get('CLOCK')
    return (clock() if clock else datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)


def stamp(value=None):
    return (value or now_utc()).astimezone(UTC).isoformat(timespec='seconds').replace('+00:00', 'Z')


def parse(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def local_input(value):
    return value.astimezone(SANTIAGO).strftime('%Y-%m-%dT%H:%M')


def parse_local(value):
    try:
        naive = datetime.strptime(value, '%Y-%m-%dT%H:%M')
    except (ValueError, TypeError):
        raise ValueError('Indica una fecha y hora válidas de devolución.') from None
    candidates = set()
    for fold in (0, 1):
        aware = naive.replace(tzinfo=SANTIAGO, fold=fold)
        utc = aware.astimezone(UTC)
        if utc.astimezone(SANTIAGO).replace(tzinfo=None) == naive:
            candidates.add(utc)
    if len(candidates) != 1:
        raise ValueError('Esa hora coincide con un cambio de horario de Chile. Elige otra hora.')
    return candidates.pop()


def display(value):
    if not value:
        return '—'
    dt = parse(value).astimezone(SANTIAGO)
    offset = dt.strftime('%z')
    return dt.strftime('%d/%m/%Y · %H:%M') + f' (UTC{offset[:3]}:{offset[3:]})'


def due_notice(loan, now=None):
    if loan['status'] != 'activo':
        return None
    now = now or now_utc()
    due = parse(loan['due_at'])
    if due < now:
        return 'Vencido'
    if due.astimezone(SANTIAGO).date() == now.astimezone(SANTIAGO).date():
        return 'Vence hoy'
    if due <= now + timedelta(hours=current_app.config['DUE_SOON_HOURS']):
        return 'Próximo a vencer'
    return None
