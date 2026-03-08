"""Strategic Swarm Agent MVP."""

__all__ = ["StrategicSwarmRunner"]


def __getattr__(name: str):
    if name == "StrategicSwarmRunner":
        from strategic_swarm_agent.graph.runner import StrategicSwarmRunner

        return StrategicSwarmRunner
    raise AttributeError(name)
