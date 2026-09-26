# Build context is ~/.raft/controller (Dockerfile + copied ``raft`` package).
# Shared with the host CLI — same Python package, different process.
FROM python:3.12-slim

WORKDIR /opt
COPY raft/ /opt/raft/
ENV PYTHONPATH=/opt

# Stub: idle until heal / scale loops land.
CMD ["python", "-m", "raft.controller"]
