from flask import Blueprint, render_template, request, g, redirect, url_for, flash, abort
from . import data
from .auth import role_required
from .db import transaction
from .errors import DomainError

bp = Blueprint('favorites',__name__)


@bp.get('/favoritos')
@role_required('alumno')
def index():
    saved = data.favorite_ids(g.user['id'])
    watched = data.watched_ids(g.user['id'])
    books = data.books()
    return render_template('favorites.html',books=[b for b in books if b['id'] in saved],
                           watched_books=[b for b in books if b['id'] in watched],
                           favorite_ids=saved,watched_ids=watched)


@bp.post('/libros/<int:book_id>/favorito',endpoint='favorite')
@bp.post('/libros/<int:book_id>/aviso',endpoint='watch')
@role_required('alumno')
def preference(book_id):
    action = request.form.get('action')
    if action not in ('add','remove'):
        raise DomainError('Selecciona guardar/activar o quitar/desactivar.',400)
    enabled = action=='add'
    watching = request.path.endswith('/aviso')
    with transaction():
        if not data.book(book_id):
            abort(404)
        if watching:
            if enabled and data.copies(book_id,True):
                raise DomainError('Este título ya tiene ejemplares disponibles. Puedes solicitarlo desde su ficha.')
            data.set_watch(g.user['id'],book_id,enabled)
        else:
            data.set_favorite(g.user['id'],book_id,enabled)
    message = ('Aviso activado.' if enabled else 'Aviso desactivado.') if watching else ('Libro guardado en Favoritos.' if enabled else 'Libro quitado de Favoritos.')
    flash(message,'success')
    destination = request.form.get('return_to')
    if destination=='favorites':
        return redirect(url_for('favorites.index'))
    if destination=='catalog':
        return redirect(url_for('catalog.index'))
    return redirect(url_for('catalog.detail',book_id=book_id))


@bp.get('/avisos')
@role_required('alumno')
def notices():
    return render_template('notifications.html',notifications=data.notifications(g.user['id']))


@bp.post('/avisos/<int:notification_id>/leido')
@role_required('alumno')
def read_notice(notification_id):
    with transaction():
        if not data.mark_notification_read(g.user['id'],notification_id):
            abort(404)
    flash('Aviso marcado como leído.','success')
    return redirect(url_for('favorites.notices'))
