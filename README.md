# Biblioteca Mejorada

Prototipo académico de Biblioteca UCN Coquimbo, vinculado al ODS 10, con datos ficticios. Python/Flask, HTML/Jinja y estilos UCN. Se publica en Cloudflare Workers y guarda los datos en D1.

Incluye alumnos y administradores, catálogo, ejemplares, solicitudes, préstamos, historial, favoritos y avisos internos. Biblioteca aprueba y prepara el retiro; el préstamo empieza al registrar la entrega física. Favoritos y avisos no reservan ejemplares.

## Publicar desde GitHub

No necesitas instalar Python en tu PC. La preparación se ejecuta en GitHub Actions.

1. Sube el contenido de esta carpeta a la raíz del repositorio, incluyendo `.github`.
2. En Cloudflare, crea una base D1 nueva llamada `biblioteca-mejorada` y un Worker inicial del mismo nombre. Guarda su Database ID, el Account ID y el dominio `biblioteca-mejorada.TU-SUBDOMINIO.workers.dev`.
3. En los secretos del Worker añade `SECRET_KEY` y `SETUP_TOKEN`: dos claves aleatorias distintas de 64 caracteres, generadas con un gestor de contraseñas. No las escribas en el código.
4. Crea un API token de Cloudflare limitado a tu cuenta, con permisos para editar el Worker y D1. En GitHub → Settings → Secrets and variables → Actions, configura:

| Tipo | Nombre | Valor |
|---|---|---|
| Secret | `CLOUDFLARE_ACCOUNT_ID` | Account ID de Cloudflare. |
| Secret | `CLOUDFLARE_API_TOKEN` | Token de publicación. |
| Variable | `CLOUDFLARE_D1_ID` | Database ID. |
| Variable | `SITE_HOST` | Dominio del Worker, sin `https://` ni `/`. |

5. Ejecuta **Actions → Publicar Biblioteca en Cloudflare → Run workflow**.
6. Abre el enlace del Worker con `/configurar`, introduce `SETUP_TOKEN` y crea tu administrador con una contraseña propia. Luego elimina `SETUP_TOKEN` de los secretos del Worker y conserva `SECRET_KEY`.
7. Entra en `/ingresar`. Desde **Alumnos** puedes crear cuentas o restablecer las de ejemplo. Las cuentas ficticias se publican desactivadas; no hay una contraseña pública de administrador.

Cada compañero puede descargar o clonar este repositorio. Para publicar una instalación independiente necesitará su propia configuración y base. Para colaborar en la misma instalación, trabajen en el mismo repositorio sin compartir los secretos en los archivos. El computador puede estar apagado una vez publicada.

## Modificar el proyecto

| Ruta | Función |
|---|---|
| `biblioteca/templates/`, `biblioteca/static/` | Pantallas, CSS y JavaScript. |
| `biblioteca/auth.py`, `security.py`, `passwords.py` | Sesiones, permisos y contraseñas. |
| `biblioteca/catalog.py`, `views.py`, `favorites.py` | Catálogo, gestión y favoritos/avisos. |
| `biblioteca/circulation.py`, `rules.py` | Solicitudes, entregas, devoluciones y reglas. |
| `biblioteca/data.py`, `db.py`, `cloud_db.py` | Consultas y persistencia SQLite/D1. |
| `biblioteca/cloud_accounts.py` | Administrador inicial y cuentas de alumnos. |
| `src/worker.py` | Entrada del servidor en Cloudflare. |
| `scripts/`, `.github/workflows/` | Preparación y publicación. |
| `cloudflare/migrations/` | Cambios de esquema de D1. |
| `pyproject.toml`, `uv.lock`, `pylock.toml`, `package*.json`, `wrangler.jsonc` | Dependencias fijadas y configuración del despliegue. |

Tras guardar cambios, vuelve a ejecutar el flujo de publicación. Mantén el mismo D1 ID para conservar los datos y la misma `SECRET_KEY` para conservar las sesiones. No borres ni reescribas migraciones aplicadas: añade nuevas. Exporta un respaldo desde D1 antes de cambios importantes. Descargar el código no descarga la base de una instalación.

Para desarrollar localmente con Python 3.12 y uv: ejecuta `uv sync --locked`, copia `.env.example` a `.env`, sustituye `SECRET_KEY` por una clave aleatoria propia y ejecuta:

```sh
uv run python -m flask --app app init-db
uv run python -m flask --app app seed-demo
uv run python -m flask --app app run
```

La inicialización y carga son explícitas, solo para una base local nueva. Los siguientes arranques usan únicamente el último comando. Abre `http://127.0.0.1:5000`. Cuentas locales: `admin@demo.test`, `ana@demo.test`, `bruno@demo.test`, `carla@demo.test`; contraseña ficticia `DemoUCN2026!`. Estas credenciales no permiten entrar en Cloudflare. El servidor de desarrollo es solo para uso local.

## Estado y límites

- Aplicación comprobada localmente; despliegue real en Cloudflare pendiente de verificación. No se ha validado su ejecución dentro del límite de CPU del plan gratuito; revisa el plan antes de publicar.
- Las pruebas automatizadas se ejecutaron durante la preparación, pero no se incluyen en este paquete mínimo ni se ejecutan automáticamente en GitHub.
- El adaptador D1 trabaja con instantáneas y control de versión, con un máximo de 10.000 filas. Está pensado para un prototipo pequeño; los conflictos concurrentes requieren actualizar y repetir la operación.
- No se incluyen agenda, renovaciones, correos, pagos ni conexión institucional. Las futuras fuentes de datos se adaptarán en la capa de datos.
- Reglas por colección: pregrado, 6 ejemplares generales y 3 de alta demanda, con plazo sugerido de 3 días; son cupos independientes. Biblioteca confirma el vencimiento al entregar. Días hábiles, feriados y sanciones requieren validación con UCN. El aviso de 48 horas es una decisión configurable del prototipo.
- Referencias: [Reglamento UCN 82/2021](https://bibliotecas.ucn.cl/wp-content/uploads/2021/08/Reglamento-Unificado-Bibliotecas-UCN-2021-Decreto-82-2021.pdf), [préstamos Coquimbo](https://bibliotecas.ucn.cl/servicios/prestamos/coquimbo/), [preguntas frecuentes](https://bibliotecas.ucn.cl/faqs/).
- No subas `.env`, tokens, bases personales ni dependencias instaladas. Conserva `.gitignore` y los archivos de versiones fijadas. Las pruebas aprobadas no garantizan seguridad completa.
