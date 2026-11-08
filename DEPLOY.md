Run `make deploy` (or plain `make`) to optimize art and upload the books.

Deployment uses `nsp-deploy@server` and the private key at
`.deploy/ssh/nsp-deploy`. That key is mode 600 and excluded from Git by the
existing `.deploy/` ignore rule. Keep it when cleaning build artifacts;
another checkout or machine needs a copy of the key or a newly authorized key.

On the server, `nsp-deploy` owns `/var/www/me/nsp` and has no extra groups or
sudo privileges. Its root-owned home is `/var/lib/nsp-deploy`. The root-owned
`.ssh/authorized_keys` uses `restrict` and forces
`/usr/local/libexec/nsp-rrsync`; shell access, forwarding, and PTYs are denied.
Remote rsync paths are relative to `/var/www/me/nsp`.

The server wrapper is maintained here as `deploy-rrsync.py`. It translates
macOS openrsync's `--dirs` to `-d`, then invokes Ubuntu's standard `rrsync`
with `-wo -munge /var/www/me/nsp`. That allows uploads and deletion within
the books directory, rejects downloads and parent-directory traversal, and
munges uploaded symlinks so they cannot target files outside it.

The normal `admin` SSH login remains available separately. The deployment
key cannot run arbitrary commands, including commands as `admin`.
