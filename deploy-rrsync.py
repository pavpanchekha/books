#!/usr/bin/python3
"""Server-side openrsync compatibility; rrsync still validates every argument.

Install root-owned at /usr/local/libexec/nsp-rrsync and force it in the
deployment key's authorized_keys entry. macOS sends --dirs, while Ubuntu's
rrsync accepts only the equivalent -d.
"""

import os
import re

command = os.environ.get("SSH_ORIGINAL_COMMAND", "")
options, separator, paths = command.partition(" . ")
options = re.sub(r"(?<!\S)--dirs(?=\s|$)", "-d", options)
os.environ["SSH_ORIGINAL_COMMAND"] = options + separator + paths
os.execv("/usr/bin/rrsync", ["rrsync", "-wo", "-munge", "/var/www/me/nsp"])
