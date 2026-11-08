"""Publish local books without deleting any other book or illustration."""
import argparse
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

from bookmaker.catalog import sync_catalog
from bookmaker.repository import index_order, update_index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--slug')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if args.slug and not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', args.slug):
        parser.error('invalid slug')
    if args.slug and not (root / f'{args.slug}.html').is_file():
        parser.error('book HTML is missing')
    local_order = index_order(root) if (root / 'index.html').exists() else []
    sync_catalog(root)
    published = index_order(root)
    if args.slug:
        selected = [f'{args.slug}.html']
    else:
        selected = [name for name in local_order if (root / name).is_file()]
        selected += [p.name for p in sorted(root.glob('*.html')) if p.name != 'index.html' and p.name not in selected]
    # Prepend new books in local catalog order. Existing books retain recency.
    for name in reversed([name for name in selected if name not in published]):
        update_index(root, name, local_filenames=set(selected))
    for name in selected:
        update_index(root, name, local_filenames=set(selected))
    command = [sys.executable, 'optimize_art.py']
    if args.slug:
        command += ['--slug', args.slug]
    subprocess.run(command, cwd=root, check=True)
    key = os.environ.get('DEPLOY_KEY_FILE', str(root / '.deploy/ssh/nsp-deploy'))
    host = os.environ.get('DEPLOY_HOST', 'nsp-deploy@pavpanchekha.com')
    ssh_args = ['ssh', '-i', key, '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes']
    if host == 'nsp-deploy@pavpanchekha.com':
        ssh_args += ['-o', f'UserKnownHostsFile={root / ".agents/known_hosts"}',
                     '-o', 'GlobalKnownHostsFile=/dev/null', '-o', 'StrictHostKeyChecking=yes']
    ssh = shlex.join(ssh_args)
    def upload(sources, destination):
        subprocess.run(['rsync', '-az', '--chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r',
                        '-e', ssh, *sources, f'{host}:{destination}'], cwd=root, check=True)
    art = root / '.deploy/art'
    if args.slug:
        art = art / args.slug
        if art.exists():
            upload([str(art)], "art/")
    elif art.exists():
        upload([str(art) + '/'], 'art/')
    upload([*selected, 'book.css', 'book.js'], './')
    # Publish the catalog last, after the book and artwork are live.
    upload(['index.html'], './')


if __name__ == '__main__':
    main()
