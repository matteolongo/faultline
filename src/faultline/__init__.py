"""Faultline MVP."""

__all__ = ["StrategicSwarmRunner"]


def __getattr__(name: str):
    if name == "StrategicSwarmRunner":
        from faultline.graph.runner import StrategicSwarmRunner

        return StrategicSwarmRunner
    raise AttributeError(name)
