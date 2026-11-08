"""Exercise real rsync uploads against an isolated HTTP-served library."""
import functools
import importlib.util
import os
from pathlib import Path
import shutil
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
    # Run the real local rsync and its real server process. Only SSH transport
    # is substituted, so the test needs no key, account, or network service.
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    ssh = bin_dir / 'ssh'
    ssh.write_text(
        '#!/usr/bin/env python3\n'
        'import os, sys, shlex\n'
        'args = sys.argv[1:]\n'
        'while args and args[0] in ("-i", "-o"):\n'
        '    args = args[2:]\n'
        'args = args[1:]\n'
        'if len(args) == 1: args = shlex.split(args[0])\n'
        'os.chdir(os.environ["TEST_REMOTE"])\n'
        'os.execvp(args[0], args)\n'
    )
    ssh.chmod(0o755)
    monkeypatch.setenv('PATH', str(bin_dir) + os.pathsep + os.environ['PATH'])
    monkeypatch.setenv('TEST_REMOTE', str(remote))
    monkeypatch.setenv('DEPLOY_HOST', 'fixture')
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
        assert index_order(remote) == ['new.html', 'old.html']
        assert (remote / 'old.html').read_text() == old
        assert (remote / 'art/old/keep.webp').read_bytes() == b'old artwork must survive'
        assert (remote / 'art/new/page.webp').read_bytes() == b'new artwork'
        assert (remote / 'new.html').read_bytes() == (checkout / 'new.html').read_bytes()
        assert (remote / 'book.css').read_bytes() == (repository / 'book.css').read_bytes()
        assert (remote / 'book.js').read_bytes() == (repository / 'book.js').read_bytes()
        index = (remote / 'index.html').read_text()
        assert '4 English words' in index
        assert 'New words (2)' in index  # New, cat; Moon is already known.
        assert not (checkout / 'old.html').exists()
        assert not (checkout / 'art/old').exists()
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
