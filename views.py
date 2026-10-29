from flask import Blueprint, render_template, request, g, redirect, url_for, flash, abort, current_app
from . import data, circulation, rules
from .auth import login_required, role_required
from .db import transaction
from .errors import DomainError
from .timeutils import due_notice, local_input

bp = Blueprint('views',__name__)


@bp.get('/')
@login_required
def home():
    if g.user['role']=='admin':
        return redirect(url_for('views.admin_requests'))
    loans = data.loans(g.user['id'],'activo')
    notices = [(loan,due_notice(loan)) for loan in loans if due_notice(loan)]
    requests = [r for r in data.requests(g.user['id']) if r['status'] in ('pendiente','aprobada')]
    return render_template('dashboard.html',loans=loans,notices=notices,requests=requests,availability_notices=data.notifications(g.user['id'],True)[:3])


@bp.get('/mis-solicitudes')
@role_required('alumno')
def my_requests():
    return render_template('requests.html',rows=data.requests(g.user['id']),admin=False,status='')


@bp.get('/mis-prestamos')
@role_required('alumno')
def my_loans():
    return render_template('loans.html',rows=data.loans(g.user['id']),admin=False,status='')


@bp.post('/libros/<int:book_id>/solicitar')
@role_required('alumno')
def submit(book_id):
    ident = circulation.submit(g.user['id'],book_id,request.form.get('collection_id',''))
    flash('Solicitud enviada. Biblioteca debe revisarla; todavía no asegura un ejemplar.','success')
    return redirect(url_for('views.request_detail',request_id=ident))


@bp.get('/solicitudes/<int:request_id>')
@login_required
def request_detail(request_id):
    row = data.request(request_id)
    if not row or (g.user['role']!='admin' and row['user_id']!=g.user['id']):
        abort(404)
    options = data.copies(row['book_id'],True,row['collection_id']) if g.user['role']=='admin' else []
    suggested = rules.suggested_due(row['user_id'],row['collection_id'])
    return render_template('request.html',row=row,options=options,suggested=local_input(suggested) if suggested else '')


@bp.post('/solicitudes/<int:request_id>/cancelar')
@login_required
def cancel(request_id):
    circulation.cancel(g.user['id'],request_id)
    flash('Solicitud cancelada. Cualquier ejemplar asignado vuelve a estar disponible.','success')
    return redirect(url_for('views.request_detail',request_id=request_id))


@bp.get('/admin/solicitudes')
@role_required('admin')
def admin_requests():
    status = request.args.get('status','pendiente')
    return render_template('requests.html',rows=data.requests(status=status),admin=True,status=status)


@bp.post('/admin/solicitudes/<int:request_id>/<action>')
@role_required('admin')
def request_action(request_id,action):
    if action=='aprobar':
        try:
            copy_id=int(request.form.get('copy_id',''))
        except ValueError:
            raise DomainError('Selecciona un ejemplar disponible.',400) from None
        circulation.approve(g.user['id'],request_id,copy_id)
        message='Ejemplar asignado. Confirma cuando esté listo para retirar.'
    elif action=='preparar':
        circulation.mark_ready(g.user['id'],request_id)
        message='El alumno ya puede ver que su ejemplar está listo para retirar.'
    elif action=='rechazar':
        circulation.reject(g.user['id'],request_id,request.form.get('reason',''))
        message='Solicitud rechazada; el motivo es visible para el alumno.'
    elif action=='entregar':
        circulation.deliver(g.user['id'],request_id,request.form.get('due_at',''),request.form.get('confirmed')=='yes')
        message='Entrega registrada. El préstamo comenzó y el vencimiento quedó confirmado.'
    else:
        abort(404)
    flash(message,'success')
    return redirect(url_for('views.request_detail',request_id=request_id))


@bp.get('/admin/prestamos')
@role_required('admin')
def admin_loans():
    status=request.args.get('status','activo')
    return render_template('loans.html',rows=data.loans(status=status),admin=True,status=status)


@bp.post('/admin/prestamos/<int:loan_id>/devolver')
@role_required('admin')
def return_loan(loan_id):
    circulation.receive(g.user['id'],loan_id)
    flash('Devolución registrada. El ejemplar está disponible y el aviso de vencimiento se eliminó.','success')
    return redirect(url_for('views.admin_loans'))


@bp.get('/admin/alumnos')
@role_required('admin')
def students():
    return render_template('students.html',students=data.students())


@bp.post('/admin/alumnos/<int:user_id>/habilitacion')
@role_required('admin')
def eligibility(user_id):
    with transaction():
        user=data.user(user_id)
        if not user or user['role']!='alumno':
            abort(404)
        active=request.form.get('account_active')=='yes'
        enabled=request.form.get('lending_enabled')=='yes'
        reason=request.form.get('reason','').strip()
        if len(reason)>500 or ((not active or not enabled) and len(reason)<3):
            raise DomainError('Registra un motivo de bloqueo de 3 a 500 caracteres.',400)
        if active and enabled:
            reason=''
        data.set_eligibility(user_id,active,enabled,reason)
        data.audit(g.user['id'],'habilitacion_actualizada',user_id,f'Activa: {active}. Préstamos: {enabled}. {reason}')
    flash('Habilitación actualizada. Se comprobará nuevamente en cada operación.','success')
    return redirect(url_for('views.students'))


@bp.get('/reglas')
@login_required
def regulations():
    return render_template('rules.html',rules=data.rules(),threshold=current_app.config['DUE_SOON_HOURS'])


@bp.get('/admin/actividad')
@role_required('admin')
def activity():
    return render_template('activity.html',events=data.audit_log())
