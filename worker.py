from functools import lru_cache
from flask import Response
from jinja2 import DictLoader
from workers import wsgi
from biblioteca import create_app
from cloud_bundle import TEMPLATES, STATIC


@lru_cache(maxsize=2)
def configured_app(secret, host, setup_token):
    app = create_app(dict(
        SECRET_KEY=secret, TRUSTED_HOSTS=[host], APP_MODE='production',
        SESSION_COOKIE_SECURE=True, CLOUD_D1=True, SETUP_TOKEN=setup_token,
    ))
    app.jinja_loader = DictLoader(TEMPLATES)

    def static_file(filename):
        if filename not in STATIC:
            return Response('No encontrado', status=404)
        content, mime = STATIC[filename]
        return Response(content, mimetype=mime)

    app.view_functions['static'] = static_file
    return app


def application(environ, start_response):
    env = environ['workers.env']
    secret = str(getattr(env, 'SECRET_KEY', ''))
    host = str(getattr(env, 'SITE_HOST', ''))
    setup_token = str(getattr(env, 'SETUP_TOKEN', ''))
    if len(secret) < 32 or not host or '/' in host:
        return Response('Falta configurar SECRET_KEY y SITE_HOST en Cloudflare.', status=503)(environ, start_response)
    # Cloudflare termina HTTPS antes de pasar la solicitud al adaptador WSGI.
    environ['wsgi.url_scheme'] = 'https'
    environ['REMOTE_ADDR'] = environ.get('HTTP_CF_CONNECTING_IP', 'unknown')
    return configured_app(secret, host, setup_token)(environ, start_response)


Default = wsgi.entrypoint(application)
