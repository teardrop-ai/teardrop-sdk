# Labeling

Labeling exposes organization-scoped definitions, predictions, and results for
agent schedules. It also supports binding a definition to a schedule and
recording an explicit score override.

```python
from teardrop import LabelingBindingRequest, ScoreResult

definitions = await client.labeling.get_definitions()
predictions = await client.labeling.get_predictions(limit=50)
results = await client.labeling.get_results(limit=50)

await client.labeling.bind_definition(
    LabelingBindingRequest(
        schedule_id="schedule-id",
        definition_key="quality-v1",
        definition_version=1,
    )
)

await client.labeling.override_result(
    "target-id",
    ScoreResult(
        label="correct",
        status="correct",
        rationale="The observed outcome matches the prediction.",
        source="manual",
    ),
)
```

The synchronous facade exposes the same methods under `client.labeling`.
Labeling endpoints use the authenticated organization associated with the
client credentials or token.

---

**Related:** [README](../README.md) · [Models Reference](models-reference.md)