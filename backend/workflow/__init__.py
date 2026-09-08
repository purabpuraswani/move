"""Phase 6: wiring `run_workflow()` (backend/orchestrator/orchestrator.py)
into the real, running application.

    workflow/assembly.py   pure: User State assembly + Need Assessment,
                            given already-fetched source documents. No
                            pymongo/bson import, so it is testable without a
                            database connection.
    workflow/response.py   pure: translating a run_workflow() result into
                            the clean, user-facing JSON shape the API
                            actually returns — never an internal
                            orchestration id, never a raw Mongo _id.

backend/routes/workflow.py is the only module in this package that talks to
MongoDB or to the real Mcp*ToolClient classes; it is a thin glue layer over
the two pure modules here.
"""

