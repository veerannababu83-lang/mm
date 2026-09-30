
# SuccessFactors Knowledge Graph POC

## Architecture

SAP SuccessFactors JSON
        |
        v
Normalize
        |
        v
Canonical ontology (`config/schema.json`)
        |
        v
Upsert vertices + relationships
        |
        v
Apache TinkerPop / TinkerGraph
        |
        v
Gremlin queries + validation
        |
        v
LLM layer later

## Important design decisions

1. API endpoints are not automatically graph entities.
2. `Employee.userId` is the canonical employee identity.
3. `personIdExternal` from PerPersonal is treated as the cross-source identity for Employee.
4. EmployeeTime records are keyed by `externalCode` when present.
5. `relationshipType` is preserved; it is not renamed to `REPORTS_TO` without business confirmation.
6. Credentials/tokens/cookies are never stored in the graph.
7. Current Candidate, JobApplication and Policy responses are not usable for data population:
   - Candidate: permission error.
   - JobApplication: empty result.
   - Policy List: authentication error.
8. This is a deterministic structured-data pipeline. Do not call an LLM for normal JSON-to-node mapping.

## Run

1. Start Gremlin Server on `ws://localhost:8182/gremlin`.
2. Install Python dependency:

   `pip install -r requirements.txt`

3. Copy the uploaded response fixtures into `fixtures/` using the exact fixture names expected by `app/ingest.py`.
4. Run:

   `python app/ingest.py`

5. Validate:

   `python app/validate.py`

## Production transition

Keep `schema.json`, normalizer, identity resolution and validation. Replace only the graph adapter:
TinkerGraph/Gremlin Server -> production graph provider (for example a TinkerPop-compatible backend).

Then add:
- API fetch layer
- retry/backoff
- pagination
- incremental sync/watermark
- dead-letter/error store
- provenance (`source_api`, `source_record_id`, `ingested_at`)
- schema versioning
- LLM natural-language-to-Gremlin layer
