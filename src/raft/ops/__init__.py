"""Operator ops: doctor, status, logs, certs, purge, update, uninstall.

Import public names from owning subpackages (``ops.certs``, ``ops.doctor``,
``ops.status``, ``ops.logs``, …). This package ``__init__`` stays import-free
so ``adapters.docker.edge`` → ``ops.certs`` cannot cycle through a fat barrel.
"""

__all__: list = []
