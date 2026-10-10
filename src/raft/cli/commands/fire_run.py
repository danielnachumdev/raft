"""Fire dispatch with fail-fast rejection of unused command args.

Google Fire parses kwargs, *calls the routine*, then errors on leftover tokens.
That prints command output (e.g. ``raft status``) before ``Could not consume
arg``. Raft never chains Fire on command return values, so leftover tokens after
parsing a routine are always invalid — reject them *before* calling.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional, Sequence, Union

import fire
from fire import core as fire_core
from fire import decorators

_ORIGINAL_CALL = fire_core._CallAndUpdateTrace


def _call_rejecting_unused(
    component,
    args,
    component_trace,
    treatment: str = "class",
    target=None,
):
    """Like Fire's ``_CallAndUpdateTrace``, but reject leftovers before routines."""
    if treatment in ("routine", "callable"):
        metadata = decorators.GetMetadata(component)
        fn = component.__call__ if treatment == "callable" else component
        parse = fire_core._MakeParseFn(fn, metadata)
        _parsed, _consumed, remaining_args, _capacity = parse(args)
        if remaining_args:
            raise fire_core.FireError("Could not consume arg:", remaining_args[0])
    return _ORIGINAL_CALL(
        component,
        args,
        component_trace,
        treatment=treatment,
        target=target,
    )


@contextmanager
def _fail_fast_unused_args() -> Iterator[None]:
    fire_core._CallAndUpdateTrace = _call_rejecting_unused
    try:
        yield
    finally:
        fire_core._CallAndUpdateTrace = _ORIGINAL_CALL


def run_fire(
    component,
    *,
    command: Optional[Union[str, Sequence[str]]] = None,
    name: Optional[str] = None,
):
    """``fire.Fire`` with unused-arg rejection before command routines run."""
    with _fail_fast_unused_args():
        return fire.Fire(component, command=command, name=name)
