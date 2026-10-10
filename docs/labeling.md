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

## External Prediction Submission and Proofs

Submit an externally signed prediction with an idempotency key. The server
assigns the prediction timestamp; callers do not supply one.

```python
from teardrop import PredictionSubmitRequest

request = PredictionSubmitRequest(
    definition_key="quality-v1",
    definition_version=1,
    idempotency_key="my-prediction-001",
    signer_address=signer_address,
    signature=signature,  # sign the canonical payload as required by the API
    predictions={"label": "good"},
)
submitted = await client.labeling.submit_prediction(request)
# A 201 new submission returns PredictionSubmitResponse (including its id).
# A 200 idempotent replay has no documented response body and returns None.
if submitted is None:
    print("Prediction was already submitted.")
else:
    print("Prediction accepted:", submitted.id)
    proof = await client.labeling.get_prediction_proof(submitted.id)
    # proof.anchor is None until the containing batch is sealed.
```

The synchronous facade exposes the same methods through `client.labeling`.
Authentication, authorization, and idempotency conflicts use the SDK's
existing `AuthenticationError`, `ForbiddenError`, and `ConflictError` mappings.

## Public Scorecards

Scorecards are available from the unauthenticated `client.scorecards` module:

```python
tasks = await client.scorecards.list_tasks()
leaderboard = await client.scorecards.get_leaderboard(
    "quality-v1",
    1,                       # definition_version is an integer
    window_days=90,
)
scorecard = await client.scorecards.get_scorecard(
    "quality-v1",
    1,
    "0x0123456789012345678901234567890123456789",
)
```

Leaderboards rank eligible subjects by coverage-adjusted Brier score (lower is
better). Each task includes a hash of its immutable definition. Below a task's
minimum sample, metric values and calibration bins are withheld; the relevant
scorecard fields are `None`. The synchronous facade mirrors these methods under
`client.scorecards`.

The synchronous facade exposes the same methods under `client.labeling`.
Labeling endpoints use the authenticated organization associated with the
client credentials or token.

---

**Related:** [README](../README.md) · [Models Reference](models-reference.md)