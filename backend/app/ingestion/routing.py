"""Which model handles which task. Changing the routing is changing data, not code.

Two strategies, both kept so the eval can compare them:

- **cheap-first** (default): the cheap model reads everything; a reading that fails verification
  is retried once on a strong model from a *different* provider. You only pay for the strong model
  when a reading actually looks wrong.
- **cautious**: strong models up front for the inputs we expected to be hard (floor plans, charts,
  photos). This was the original design.

The eval (`evals/run.py`) decided between them: on the dataset, the cheap model alone scored 100%
at ~1/7 of the cost (DECISIONS [016]). Re-run it when the documents get harder.
"""

from dataclasses import asdict, dataclass, replace


@dataclass(frozen=True)
class Routing:
    text: str = "anthropic/claude-haiku-5.5"
    triage: str = "anthropic/claude-haiku-5.5"
    floor_plan: str = "anthropic/claude-haiku-5.5"
    chart: str = "anthropic/claude-haiku-5.5"
    document_photo: str = "anthropic/claude-haiku-5.5"
    escalation: str = "openai/gpt-6.1-sol"

    def as_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def single_model(cls, model: str) -> "Routing":
        """Every task on one model — the baseline the eval compares routing against."""
        return cls(model, model, model, model, model, model)


CAUTIOUS = Routing(
    floor_plan="anthropic/claude-sonnet-5.5",
    chart="anthropic/claude-sonnet-5.5",
    document_photo="anthropic/claude-sonnet-5.5",
)

# OpenAI direct (no OpenRouter key) can only reach OpenAI models.
OPENAI_CHEAP_FIRST = Routing(
    text="openai/gpt-6-luna",
    triage="openai/gpt-6-luna",
    floor_plan="openai/gpt-6-luna",
    chart="openai/gpt-6-luna",
    document_photo="openai/gpt-6-luna",
    escalation="openai/gpt-6.1-sol",
)
OPENAI_CAUTIOUS = replace(
    OPENAI_CHEAP_FIRST,
    floor_plan="openai/gpt-6.1-sol",
    chart="openai/gpt-6.1-sol",
    document_photo="openai/gpt-6.1-sol",
    escalation="openai/gpt-6-astra",
)


def default_routing(provider: str) -> Routing:
    return OPENAI_CHEAP_FIRST if provider == "openai" else Routing()


def cautious_routing(provider: str) -> Routing:
    return OPENAI_CAUTIOUS if provider == "openai" else CAUTIOUS


def with_overrides(routing: Routing, **models: str) -> Routing:
    return replace(routing, **{task: model for task, model in models.items() if model})
