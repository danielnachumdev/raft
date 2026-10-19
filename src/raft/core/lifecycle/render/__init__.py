"""Render Compose + nginx artifacts under generated/.

Import cutover/orchestrator consumers from owning modules when needed so
``from raft.core.lifecycle.render import StackRenderer`` stays acyclic with deploy/acme.
"""

from .compose_apps import ComposeAppsYaml, compose_str
from .env_file_path import ComposeEnvFilePath
from .fragment_collector import FragmentCollector
from .gate_nginx import GateNginxStamp
from .router_nginx import RouterNginxStamp
from .scaling_gate import ScalingGate
from .scaling_holding import ScalingHoldingPages
from .stack_renderer import StackRenderer

__all__ = [
    "ComposeAppsYaml",
    "ComposeEnvFilePath",
    "FragmentCollector",
    "GateNginxStamp",
    "RouterNginxStamp",
    "ScalingGate",
    "ScalingHoldingPages",
    "StackRenderer",
    "compose_str",
]
