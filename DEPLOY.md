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

## Publish from a partial checkout

Copy the deploy key securely to the new machine, install Python, `uv`, rsync,
SSH and `cwebp`, and run `uv sync`. No `server` SSH alias is required now.
`DEPLOY_KEY` and `DEPLOY_HOST` can override the defaults. Verify the server's
SSH host key on the new machine before deploying.

Run `make sync-catalog` before writing to load the live index and vocabulary.
It fetches published HTML over public HTTPS, retains only title/token metadata
in ignored `.deploy/catalog.json`, and keeps no older book pages or artwork.
It refreshes local `index.html` from the live website.

Create just the new book's HTML and `art/<slug>/`, then run:

```sh
make deploy SLUG=space-cats
```

This refreshes the live catalog, compresses and uploads only that book's art,
then uploads its HTML and shared CSS/JS, and uploads the merged index last.
Existing books retain their order; new books go first. Counts and new-word
lists are rebuilt using published text plus local book text. Missing catalog
metadata causes an error rather than silently dropping entries.

Plain `make` publishes the locally available books with the same catalog merge.
Neither form deletes remote artwork; obsolete files can remain on the server.
`make book SLUG=... IDEA='...'` syncs the catalog before generation and deploys
only the resulting book. `bookmaker build ... --deploy` also deploys one book.

Deploy from one device at a time: catalog refresh and upload are not a server
transaction, so simultaneous publishers can overwrite each other's index.
