"""Datos ficticios y fechas relativas. Nunca se ejecuta durante el arranque."""
from datetime import timedelta
from flask import current_app
from werkzeug.security import generate_password_hash
from . import data
from .db import transaction
from .errors import DomainError
from .timeutils import now_utc, stamp, SANTIAGO

TITLES = [
    ('Fundamentos de cálculo','Elena Mistral','Matemáticas'),
    ('Probabilidad para comprender el mundo','Tomás Vega','Matemáticas'),
    ('Estructuras de datos en práctica','Paula Ríos','Computación'),
    ('Diseño digital paso a paso','Martín Salas','Computación'),
    ('Ingeniería para un futuro sostenible','Lucía Marín','Sostenibilidad'),
    ('Álgebra lineal aplicada','Andrés Torres','Matemáticas'),
    ('Física: movimiento y energía','Valentina Soto','Ciencias'),
    ('Introducción a las bases de datos','Diego Araya','Computación'),
    ('Economía y sociedad','Camila Solís','Ciencias sociales'),
    ('Química en nuestro entorno','Sergio Molina','Ciencias'),
    ('Comunicación académica','Isabel Fuentes','Humanidades'),
    ('Ecología de la costa chilena','Javier Lagos','Sostenibilidad'),
    ('Métodos de investigación','Francisca Luna','Ciencias sociales'),
    ('Programación con Python','Rafael Oliva','Computación'),
    ('Ética y responsabilidad profesional','Antonia Vera','Humanidades'),
    ('Estadística para la ingeniería','Matías Prado','Matemáticas'),
    ('Accesibilidad y diseño universal','Daniela Campos','Sostenibilidad'),
    ('Historia del Norte Chico','Felipe Vidal','Humanidades'),
]
DEMO_PASSWORD = 'DemoUCN2026!'


def seed_demo():
    if current_app.config['APP_MODE']=='production':
        raise DomainError('Los ejemplos solo se cargan en modo local. Crea cuentas propias para publicar.')
    now = now_utc()
    original_clock = current_app.config.get('CLOCK')
    try:
        with transaction():
            if data.metadata('demo_seeded_at') or data.one('SELECT count(*) AS n FROM users')['n'] or data.one('SELECT count(*) AS n FROM books')['n']:
                raise DomainError('La base ya contiene datos. No se cargaron ejemplos ni se modificó nada.')
            password = generate_password_hash(DEMO_PASSWORD)
            admin = data.add_user('admin@demo.test','María Demo',password,role='admin',is_demo=True)
            ana = data.add_user('ana@demo.test','Ana Pérez Demo',password,is_demo=True)
            bruno = data.add_user('bruno@demo.test','Bruno Díaz Demo',password,is_demo=True)
            carla = data.add_user('carla@demo.test','Carla Muñoz Demo',password,is_demo=True)
            books, copies, collections = [], [], []
            for i,(title,author,category) in enumerate(TITLES):
                book_id=data.add_book(dict(title=title,author=author,category=category,isbn=f'DEMO-{i+1:03d}',publication_year=2020+i%6,
                    description='Título y autor ficticios para demostrar el catálogo. Material de apoyo al aprendizaje, la consulta y el trabajo universitario. No representa existencias reales de la Biblioteca UCN.'))
                collection='alta_demanda' if i in (2,4,12,14,16) else 'general'
                items=[]
                for j in range(3 if i<6 else 2):
                    items.append(data.add_copy(book_id,f'COQ-DEMO-{i+1:03d}-{j+1:02d}',collection,f'Campus Guayacán · Estante {chr(65+i//4)}-{i%4+1}'))
                books.append(book_id); copies.append(items); collections.append(collection)

            def scenario(student, index, state='pendiente', ready=False, due=None, returned=False):
                # Fechas históricas coherentes, manteniendo todos los disparadores.
                current_app.config['CLOCK'] = lambda: now-timedelta(days=7)
                ident=data.add_request(student,books[index],collections[index])
                if state in ('aprobada','atendida'):
                    current_app.config['CLOCK'] = lambda: now-timedelta(days=6)
                    data.approve_request(ident,copies[index][0])
                    if ready or state=='atendida':
                        data.ready_request(ident)
                    if state=='atendida':
                        loan_id=data.add_loan(data.request(ident),stamp(due))
                        if returned:
                            current_app.config['CLOCK'] = lambda: now-timedelta(days=3)
                            data.return_loan(loan_id)
                elif state in ('rechazada','cancelada'):
                    data.close_request(ident,state,'No fue posible preparar el material solicitado. Caso de demostración.' if state=='rechazada' else '')
                return ident

            scenario(ana,0,'atendida',due=now+timedelta(hours=30))
            end_today=now.astimezone(SANTIAGO).replace(hour=23,minute=59,second=59)
            scenario(ana,1,'atendida',due=end_today)
            scenario(bruno,2,'atendida',due=now-timedelta(days=1,hours=2))
            scenario(ana,3,'aprobada')
            scenario(ana,4,'aprobada',ready=True)
            scenario(carla,6,'aprobada',ready=True)
            scenario(carla,7)
            scenario(bruno,8)
            scenario(bruno,9,'cancelada')
            scenario(bruno,10,'rechazada')
            scenario(bruno,11,'atendida',due=now-timedelta(days=2),returned=True)
            current_app.config['CLOCK'] = lambda: now
            data.set_eligibility(carla,True,False,'Bloqueo ficticio para validar solicitudes y entregas.')
            data.retire_copy(copies[17][-1],'Deterioro físico. Caso ficticio de demostración.')
            for copy_id in copies[2][1:]:
                data.retire_copy(copy_id,'Ejemplo de título sin disponibilidad para probar los avisos.')
            data.mark_seeded()
            data.audit(admin,'demostracion_cargada',0,'18 títulos; 42 ejemplares; cuentas y operaciones ficticias.')
    finally:
        if original_clock is None:
            current_app.config.pop('CLOCK',None)
        else:
            current_app.config['CLOCK']=original_clock
