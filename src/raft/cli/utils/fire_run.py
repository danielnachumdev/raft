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


class _RejectingFireCall:
    """Fire ``_CallAndUpdateTrace`` hook that rejects leftover args first."""

    def __init__(self, stock, reject) -> None:
        self._stock = stock
        self._reject = reject

    def __call__(
        self,
        component,
        args,
        component_trace,
        treatment: str = "class",
        target=None,
    ):
        self._reject(component, args, treatment)
        return self._stock(
            component, args, component_trace, treatment=treatment, target=target
        )


class FireRunner:
    """Run ``fire.Fire`` with unused-arg rejection before command routines."""

    def run(
        self,
        component,
        *,
        command: Optional[Union[str, Sequence[str]]] = None,
        name: Optional[str] = None,
    ):
        with self._fail_fast_unused_args():
            return fire.Fire(component, command=command, name=name)

    @contextmanager
    def _fail_fast_unused_args(self) -> Iterator[None]:
        stock = fire_core._CallAndUpdateTrace
        fire_core._CallAndUpdateTrace = _RejectingFireCall(
            stock, self._reject_unused_routine_args
        )
        try:
            yield
        finally:
            fire_core._CallAndUpdateTrace = stock

    def _reject_unused_routine_args(self, component, args, treatment: str) -> None:
        if treatment not in ("routine", "callable"):
            return
        metadata = decorators.GetMetadata(component)
        fn = component.__call__ if treatment == "callable" else component
        parse = fire_core._MakeParseFn(fn, metadata)
        _parsed, _consumed, remaining_args, _capacity = parse(args)
        if remaining_args:
            raise fire_core.FireError("Could not consume arg:", remaining_args[0])
