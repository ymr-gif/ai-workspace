from services.integrations.base import AbstractConnector

REGISTRY: dict[str, type[AbstractConnector]] = {}


def register(cls: type[AbstractConnector]) -> type[AbstractConnector]:
    REGISTRY[cls.connector_type()] = cls
    return cls


def get_connector(connector_type: str) -> type[AbstractConnector]:
    cls = REGISTRY.get(connector_type)
    if not cls:
        raise ValueError(f"Unknown connector type: {connector_type}")
    return cls
