"""GitHub Actions configura identificadores públicos; nunca escribe secretos al repo."""
import json
import os
from pathlib import Path
import re

path = Path('wrangler.jsonc')
config = json.loads(path.read_text())
database = os.environ['CLOUDFLARE_D1_ID'].strip()
host = os.environ['SITE_HOST'].strip().lower()
if not re.fullmatch(r'[0-9a-fA-F-]{36}', database) or database == '00000000-0000-0000-0000-000000000000':
    raise SystemExit('Configura CLOUDFLARE_D1_ID con el UUID de tu base D1.')
if not re.fullmatch(r'[a-z0-9.-]+\.workers\.dev', host):
    raise SystemExit('SITE_HOST debe ser biblioteca-mejorada.TU-SUBDOMINIO.workers.dev, sin https:// ni rutas.')
config['d1_databases'][0]['database_id'] = database
config['vars']['SITE_HOST'] = host
path.write_text(json.dumps(config, indent=2)+'\n')
