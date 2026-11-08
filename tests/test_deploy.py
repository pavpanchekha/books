"""Exercise real rsync uploads against an isolated HTTP-served library."""
import functools
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from bookmaker.catalog import sync_catalog
from bookmaker.repository import index_order


def test_new_book_from_partial_checkout(tmp_path, monkeypatch):
    repository = Path(__file__).resolve().parents[1]
    remote = tmp_path / 'remote'
    checkout = tmp_path / 'checkout'
    remote.mkdir()
    checkout.mkdir()
    for name in ['deploy.py', 'Makefile', 'optimize_art.py', 'book.css', 'book.js']:
        shutil.copy(repository / name, checkout / name)
    shutil.copytree(repository / 'bookmaker', checkout / 'bookmaker')
    (checkout / '.agents').mkdir()
    shutil.copy(repository / '.agents/known_hosts', checkout / '.agents/known_hosts')
    # Older content exists exclusively on the server.
    old = '<section class="book"><h1>Old Moon</h1><p class="story">Moon rock.</p></section>'
    (remote / 'old.html').write_text(old)
    (remote / 'index.html').write_text(
        '<ol class="book-list"><li><a href="old.html">Old Moon</a></li></ol>'
    )
    (remote / 'art/old').mkdir(parents=True)
    (remote / 'art/old/keep.webp').write_bytes(b'old artwork must survive')
    (checkout / 'new.html').write_text(
        '<section class="book"><h1>New Moon</h1><p class="story">Moon cat.</p>'
        '<img src="art/new/page.webp"></section>'
    )
    (checkout / 'art/new').mkdir(parents=True)
    (checkout / 'art/new/page.webp').write_bytes(b'new artwork')
    (checkout / 'art/new').chmod(0o700)
    (checkout / 'art/new/page.webp').chmod(0o600)
    # Run the real local rsync and its real server process. Only SSH transport
    # is substituted, so the test needs no key, account, or network service.
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    ssh = bin_dir / 'ssh'
    ssh.write_text(
        '#!/usr/bin/env python3\n'
        'import os, sys, shlex\n'
        'args = sys.argv[1:]\n'
        'pin = os.environ.get("TEST_PIN")\n'
        'if pin:\n'
        '    assert os.path.isfile(pin)\n'
        '    assert "UserKnownHostsFile=" + pin in args\n'
        '    assert "GlobalKnownHostsFile=/dev/null" in args\n'
        '    assert "StrictHostKeyChecking=yes" in args\n'
        'else:\n'
        '    assert not any(arg.startswith("UserKnownHostsFile=") for arg in args)\n'
        'for index, arg in enumerate(args):\n'
        '    if arg == "-i":\n'
        '        with open(os.environ["TEST_IDENTITY_LOG"], "w") as log:\n'
        '            log.write(args[index + 1])\n'
        '        break\n'
        'while args and args[0] in ("-i", "-o", "-l"):\n'
        '    args = args[2:]\n'
        'args = args[1:]\n'
        'if len(args) == 1: args = shlex.split(args[0])\n'
        'os.chdir(os.environ["TEST_REMOTE"])\n'
        'os.execvp(args[0], args)\n'
    )
    ssh.chmod(0o755)
    monkeypatch.setenv('PATH', str(bin_dir) + os.pathsep + os.environ['PATH'])
    monkeypatch.setenv('TEST_REMOTE', str(remote))
    monkeypatch.setenv('TEST_IDENTITY_LOG', str(tmp_path / 'identity-path'))
    monkeypatch.setenv('DEPLOY_HOST', 'fixture')
    monkeypatch.setenv('DEPLOY_KEY', 'SYNTHETIC_PRIVATE_KEY_CONTENT')
    monkeypatch.setenv('DEPLOY_KEY_FILE', str(tmp_path / 'private-key'))
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(remote))
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        spec = importlib.util.spec_from_file_location('deploy_test_module', checkout / 'deploy.py')
        deploy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(deploy)
        site = f'http://127.0.0.1:{server.server_port}/'
        monkeypatch.setattr(deploy, 'sync_catalog', lambda root: sync_catalog(root, site))
        monkeypatch.setattr('sys.argv', ['deploy.py', '--slug', 'new'])
        deploy.main()
        assert (tmp_path / 'identity-path').read_text() == str(tmp_path / 'private-key')
        assert index_order(remote) == ['new.html', 'old.html']
        assert (remote / 'old.html').read_text() == old
        assert (remote / 'art/old/keep.webp').read_bytes() == b'old artwork must survive'
        assert (remote / 'art/new/page.webp').read_bytes() == b'new artwork'
        assert (remote / 'art/new').stat().st_mode & 0o777 == 0o755
        assert (remote / 'art/new/page.webp').stat().st_mode & 0o777 == 0o644
        assert (remote / 'new.html').read_bytes() == (checkout / 'new.html').read_bytes()
        assert (remote / 'book.css').read_bytes() == (repository / 'book.css').read_bytes()
        assert (remote / 'book.js').read_bytes() == (repository / 'book.js').read_bytes()
        index = (remote / 'index.html').read_text()
        assert '4 English words' in index
        assert 'New words (2)' in index  # New, cat; Moon is already known.
        assert not (checkout / 'old.html').exists()
        assert not (checkout / 'art/old').exists()
        # The default host must use the pinned key, unlike an overridden host.
        monkeypatch.delenv('DEPLOY_HOST')
        monkeypatch.setenv('TEST_PIN', str(checkout / '.agents/known_hosts'))
        deploy.main()
        monkeypatch.setenv('DEPLOY_HOST', 'fixture')
        monkeypatch.delenv('TEST_PIN')
        # Updating the same book keeps its position and never duplicates it.
        deploy.main()
        assert index_order(remote) == ['new.html', 'old.html']
        # Shared UI changes also work with no local book HTML or art at all.
        (checkout / 'new.html').unlink()
        shutil.rmtree(checkout / 'art')
        shutil.rmtree(checkout / '.deploy/art')
        (checkout / 'book.css').write_text('/* updated shared UI */')
        monkeypatch.setattr('sys.argv', ['deploy.py'])
        deploy.main()
        assert index_order(remote) == ['new.html', 'old.html']
        assert (remote / 'book.css').read_text() == '/* updated shared UI */'
        assert (remote / 'art/old/keep.webp').read_bytes() == b'old artwork must survive'
        assert (remote / 'art/new/page.webp').read_bytes() == b'new artwork'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_resume_materializes_valid_private_key_with_or_without_final_newline(tmp_path):
    repository = Path(__file__).resolve().parents[1]
    checkout = tmp_path / 'checkout'
    checkout.mkdir()
    subprocess.run(['git', 'init', '-q', str(checkout)], check=True)
    key = tmp_path / 'synthetic-key'
    subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)], check=True)
    secret = key.read_text()
    for value in (secret.rstrip('\n'), secret):
        subprocess.run([str(repository / '.agents/resume')], cwd=checkout,
                       env={**os.environ, 'DEPLOY_KEY': value}, check=True)
        materialized = checkout / '.deploy/ssh/nsp-deploy'
        subprocess.run(['ssh-keygen', '-y', '-P', '', '-f', str(materialized)],
                       stdout=subprocess.DEVNULL, check=True)
        assert (checkout / '.deploy').stat().st_mode & 0o777 == 0o700
        assert materialized.parent.stat().st_mode & 0o777 == 0o700
        assert materialized.stat().st_mode & 0o777 == 0o600
