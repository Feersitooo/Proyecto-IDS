import re
from flask import Blueprint, render_template, request, g, redirect, url_for, flash, abort
from . import data
from .auth import login_required, role_required
from .db import transaction
from .errors import DomainError

bp = Blueprint('catalog', __name__)


def text_field(form, name, label, maximum, required=True):
    value = form.get(name, '').strip()
    if (required and not value) or len(value) > maximum:
        raise DomainError(f'{label}: escribe entre {1 if required else 0} y {maximum} caracteres.', 400)
    return value


@bp.get('/catalogo')
@login_required
def index():
    q = request.args.get('q','').strip()[:180]
    category = request.args.get('category','')[:80]
    availability = request.args.get('availability','')
    return render_template('catalog.html', books=data.books(q,category,availability), categories=data.categories(), q=q, category=category, availability=availability, favorite_ids=data.favorite_ids(g.user['id']))


@bp.get('/libros/<int:book_id>')
@login_required
def detail(book_id):
    book = data.book(book_id)
    if not book:
        abort(404)
    items = data.copies(book_id)
    options = [c for c in data.collections() if any(i['state']=='disponible' and i['collection_id']==c['id'] for i in items)]
    return render_template('book.html', book=book, copies=items, options=options, available=sum(i['state']=='disponible' for i in items), already_open=data.has_open_title(g.user['id'],book_id) or data.has_borrowed_title(g.user['id'],book_id), is_favorite=book_id in data.favorite_ids(g.user['id']), is_watched=book_id in data.watched_ids(g.user['id']))


@bp.route('/admin/libros/nuevo', methods=['GET','POST'])
@bp.route('/admin/libros/<int:book_id>/editar', methods=['GET','POST'])
@role_required('admin')
def book_form(book_id=None):
    book = data.book(book_id) if book_id else {}
    if book_id and not book:
        abort(404)
    error = None
    if request.method == 'POST':
        book = dict(request.form)
        try:
            values = {name:text_field(request.form,name,label,limit,required) for name,label,limit,required in (
                ('title','Título',180,True),('author','Autor',180,True),('category','Categoría',80,True),('isbn','ISBN / referencia',30,False),('description','Descripción',2000,False))}
            year = request.form.get('publication_year','').strip()
            if year and (not re.fullmatch(r'\d{4}',year) or not 1000 <= int(year) <= 2100):
                raise DomainError('El año debe estar entre 1000 y 2100.',400)
            values['publication_year'] = int(year) if year else None
            with transaction():
                if book_id:
                    data.edit_book(book_id,values)
                else:
                    book_id = data.add_book(values)
                data.audit(g.user['id'],'libro_guardado',book_id)
            flash('Datos del libro guardados.','success')
            return redirect(url_for('catalog.detail',book_id=book_id))
        except DomainError as exc:
            error = exc.message
    return render_template('book_form.html',book=book,book_id=book_id,error=error), (400 if error else 200)


@bp.route('/admin/libros/<int:book_id>/ejemplares/nuevo', methods=['GET','POST'])
@bp.route('/admin/libros/<int:book_id>/ejemplares/<int:copy_id>/editar', methods=['GET','POST'])
@role_required('admin')
def copy_form(book_id,copy_id=None):
    book = data.book(book_id)
    item = data.copy(copy_id) if copy_id else {}
    if not book or (copy_id and (not item or item['book_id']!=book_id)):
        abort(404)
    error = None
    if request.method=='POST':
        try:
            code = text_field(request.form,'code','Identificador',40)
            location = text_field(request.form,'location','Ubicación',120)
            collection_id = request.form.get('collection_id','')
            if collection_id not in {c['id'] for c in data.collections()}:
                raise DomainError('Selecciona una colección válida.',400)
            with transaction():
                if copy_id:
                    if data.copy(copy_id)['state'] != 'disponible':
                        raise DomainError('Solo puedes editar un ejemplar disponible. Cancela la asignación o registra su devolución primero.')
                    data.edit_copy(copy_id,code,collection_id,location)
                else:
                    copy_id = data.add_copy(book_id,code,collection_id,location)
                data.audit(g.user['id'],'ejemplar_guardado',copy_id)
            flash('Ejemplar guardado.','success')
            return redirect(url_for('catalog.detail',book_id=book_id))
        except DomainError as exc:
            error = exc.message
            item = dict(request.form)
    return render_template('copy_form.html',book=book,item=item,copy_id=copy_id,collections=data.collections(),error=error), (400 if error else 200)


@bp.post('/admin/ejemplares/<int:copy_id>/baja')
@role_required('admin')
def retire(copy_id):
    reason = text_field(request.form,'reason','Motivo de baja',500)
    with transaction():
        item = data.copy(copy_id)
        if not item:
            abort(404)
        if item['state'] != 'disponible':
            raise DomainError('Solo se puede dar de baja un ejemplar disponible; resuelve primero su asignación o préstamo.')
        data.retire_copy(copy_id,reason)
        data.audit(g.user['id'],'ejemplar_dado_de_baja',copy_id,reason)
    flash('Ejemplar dado de baja. Se conserva su historial.','success')
    return redirect(url_for('catalog.detail',book_id=item['book_id']))
