"""Casos de uso atómicos. Cada operación relee el estado dentro de la transacción."""
from . import data, rules
from .db import transaction
from .errors import DomainError
from .timeutils import stamp, parse_local, now_utc


def require_admin(actor_id):
    actor = data.user(actor_id)
    if not actor or actor['role'] != 'admin' or not actor['account_active']:
        raise DomainError('Solo biblioteca puede realizar esta acción.', 403)


def get_request(request_id):
    req = data.request(request_id)
    if not req:
        raise DomainError('Solicitud no encontrada.', 404)
    return req


def submit(user_id, book_id, collection_id):
    with transaction():
        rules.capacity(user_id, collection_id)
        if not data.book(book_id):
            raise DomainError('Libro no encontrado.', 404)
        if data.has_open_title(user_id, book_id) or data.has_borrowed_title(user_id, book_id):
            raise DomainError('Ya tienes una solicitud activa o un préstamo activo de este título.')
        if not data.copies(book_id, True, collection_id):
            raise DomainError('Ya no hay ejemplares disponibles en esta colección. Vuelve a consultar el catálogo.')
        ident = data.add_request(user_id, book_id, collection_id)
        data.audit(user_id, 'solicitud_creada', ident)
        return ident


def approve(actor_id, request_id, copy_id):
    with transaction():
        require_admin(actor_id)
        req = get_request(request_id)
        if req['status'] != 'pendiente':
            raise DomainError('Solo se puede aprobar una solicitud pendiente.')
        rules.capacity(req['user_id'], req['collection_id'])
        item = data.copy(copy_id)
        if not item or item['state'] != 'disponible' or item['book_id'] != req['book_id'] or item['collection_id'] != req['collection_id']:
            raise DomainError('Ese ejemplar ya no está disponible o no corresponde a la solicitud.')
        data.approve_request(request_id, copy_id)
        data.audit(actor_id, 'solicitud_aprobada', request_id, item['code'])


def mark_ready(actor_id, request_id):
    with transaction():
        require_admin(actor_id)
        req = get_request(request_id)
        if req['status'] != 'aprobada' or req['ready_at']:
            raise DomainError('La solicitud debe estar aprobada y aún en preparación.')
        rules.capacity(req['user_id'], req['collection_id'], request_id)
        item = data.copy(req['copy_id'])
        if item['state'] != 'asignado':
            raise DomainError('El ejemplar no está asignado para retiro.')
        data.ready_request(request_id)
        data.audit(actor_id, 'listo_para_retiro', request_id)


def reject(actor_id, request_id, reason):
    reason = reason.strip()
    if not 3 <= len(reason) <= 500:
        raise DomainError('Escribe un motivo de rechazo entre 3 y 500 caracteres.', 400)
    with transaction():
        require_admin(actor_id)
        req = get_request(request_id)
        if req['status'] != 'pendiente':
            raise DomainError('Solo se puede rechazar una solicitud pendiente.')
        data.close_request(request_id, 'rechazada', reason)
        data.audit(actor_id, 'solicitud_rechazada', request_id, reason)


def cancel(actor_id, request_id):
    with transaction():
        req = get_request(request_id)
        actor = data.user(actor_id)
        if not actor or (req['user_id'] != actor_id and actor['role'] != 'admin'):
            raise DomainError('Solicitud no encontrada.', 404)
        if not actor['account_active']:
            raise DomainError('Cuenta inactiva.', 403)
        if req['status'] not in ('pendiente','aprobada'):
            raise DomainError('No se puede cancelar: una entrega se cierra registrando la devolución.')
        data.close_request(request_id, 'cancelada')
        data.audit(actor_id, 'solicitud_cancelada', request_id)


def deliver(actor_id, request_id, local_due, confirmed):
    if not confirmed:
        raise DomainError('Confirma la entrega física y la fecha de devolución.', 400)
    try:
        due = parse_local(local_due)
    except ValueError as exc:
        raise DomainError(str(exc), 400) from exc
    with transaction():
        require_admin(actor_id)
        req = get_request(request_id)
        if req['status'] != 'aprobada' or not req['ready_at']:
            raise DomainError('Primero aprueba la solicitud y confirma que está lista para retiro.')
        rules.capacity(req['user_id'], req['collection_id'], request_id)
        if data.copy(req['copy_id'])['state'] != 'asignado':
            raise DomainError('El ejemplar no está asignado a una solicitud vigente.')
        if due <= now_utc():
            raise DomainError('La devolución debe fijarse en una fecha y hora futuras.', 400)
        ident = data.add_loan(req, stamp(due))
        data.audit(actor_id, 'entrega_registrada', ident, 'Vencimiento UTC: ' + stamp(due))
        return ident


def receive(actor_id, loan_id):
    with transaction():
        require_admin(actor_id)
        loan = data.loan(loan_id)
        if not loan:
            raise DomainError('Préstamo no encontrado.', 404)
        if loan['status'] != 'activo':
            raise DomainError('Este préstamo ya fue devuelto.')
        data.return_loan(loan_id)
        data.audit(actor_id, 'devolucion_registrada', loan_id)
