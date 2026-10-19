"""Which model handles which task. Changing the routing is changing data, not code.

The defaults are a starting point: cheap models where the input is easy (native text, triage),
strong models where reading is hard (floor plans, charts, photos), and a model from a *different*
provider for escalation, so a retry gets a second opinion instead of the same mistake.
The eval (`evals/run.py`) is what should confirm or change these choices.
"""

from dataclasses import asdict, dataclass, replace


@dataclass(frozen=True)
class Routing:
    text: str = "anthropic/claude-haiku-5.5"
    triage: str = "anthropic/claude-haiku-5.5"
    floor_plan: str = "anthropic/claude-sonnet-5.5"
    chart: str = "anthropic/claude-sonnet-5.5"
    document_photo: str = "anthropic/claude-sonnet-5.5"
    escalation: str = "openai/gpt-6.1-sol"

    def as_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def single_model(cls, model: str) -> "Routing":
        """Every task on one model — the baseline the eval compares routing against."""
        return cls(model, model, model, model, model, model)


# OpenAI direct (no OpenRouter key) can only reach OpenAI models.
OPENAI_ONLY = Routing(
    text="openai/gpt-6-luna",
    triage="openai/gpt-6-luna",
    floor_plan="openai/gpt-6.1-sol",
    chart="openai/gpt-6.1-sol",
    document_photo="openai/gpt-6.1-sol",
    escalation="openai/gpt-6-astra",  # strongest OpenAI model; only used for failed readings
)


def default_routing(provider: str) -> Routing:
    return OPENAI_ONLY if provider == "openai" else Routing()


def with_overrides(routing: Routing, **models: str) -> Routing:
    return replace(routing, **{task: model for task, model in models.items() if model})
