import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from incidentlens.contracts import Evidence


class ToolExecutionError(RuntimeError):
    """Raised when a permitted tool fails after argument validation."""


class UnknownToolError(ValueError):
    """Raised when the model asks for a tool outside the registry."""


class IncidentFixtureArgs(BaseModel):
    incident_id: str = Field(min_length=1)


class IncidentFixtureResult(BaseModel):
    incident_id: str
    evidence: list[Evidence]
    truncated: bool = False


class ToolSpec(BaseModel):
    name: str
    description: str
    args_schema: type[BaseModel]
    result_schema: type[BaseModel]
    handler: Callable[[BaseModel], BaseModel]

    model_config = {"arbitrary_types_allowed": True}

    def model_tool_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.args_schema.model_json_schema(),
        }


class ToolRegistry:
    def __init__(self, tools: list[ToolSpec]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    @property
    def tool_names(self) -> set[str]:
        return set(self._tools)

    def restrict_to(self, allowed_names: set[str]) -> "ToolRegistry":
        """Return a registry containing only the explicitly allowed tools."""
        unknown = allowed_names - self.tool_names
        if unknown:
            raise UnknownToolError(f"unknown tools in allowlist: {sorted(unknown)}")
        return ToolRegistry([self._tools[name] for name in sorted(allowed_names)])

    def model_tool_schemas(self) -> list[dict[str, Any]]:
        return [tool.model_tool_schema() for tool in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any]) -> BaseModel:
        tool = self._tools.get(name)
        if tool is None:
            raise UnknownToolError(f"unknown tool requested: {name}")

        args = tool.args_schema.model_validate(arguments)
        result = tool.handler(args)
        return tool.result_schema.model_validate(result)


class FixtureStore:
    def __init__(self, fixture_path: Path) -> None:
        self._fixture_path = fixture_path

    def lookup_incident_fixture(self, args: IncidentFixtureArgs) -> IncidentFixtureResult:
        try:
            raw = json.loads(self._fixture_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ToolExecutionError(f"could not read fixture: {self._fixture_path}") from exc

        if raw.get("incident_id") != args.incident_id:
            raise ToolExecutionError(f"fixture not found for incident_id={args.incident_id}")

        return IncidentFixtureResult.model_validate(raw)


def build_fixture_registry(fixture_path: Path) -> ToolRegistry:
    store = FixtureStore(fixture_path)
    return ToolRegistry(
        [
            ToolSpec(
                name="lookup_incident_fixture",
                description="Read a bounded synthetic incident fixture by incident ID.",
                args_schema=IncidentFixtureArgs,
                result_schema=IncidentFixtureResult,
                handler=store.lookup_incident_fixture,
            )
        ]
    )


def is_validation_error(exc: Exception) -> bool:
    return isinstance(exc, ValidationError)
