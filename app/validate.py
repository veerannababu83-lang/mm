
import json
from pathlib import Path
from gremlin_python.structure.graph import Graph
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection

SCHEMA = json.loads(Path(__file__).resolve().parents[1].joinpath("config/schema.json").read_text())

def validate(g):
    errors = []

    for label, spec in SCHEMA["entities"].items():
        if spec.get("status"):
            continue
        missing = g.V().hasLabel(label).not_(__.has("graph_id")).count().next()
        if missing:
            errors.append(f"{label}: {missing} vertices missing graph_id")

    # Required cross-entity relationships for the POC.
    for label in ["EmployeeTime", "PersonalInfo"]:
        orphan_count = g.V().hasLabel(label).not_(__.inE()).count().next()
        if orphan_count:
            errors.append(f"{label}: {orphan_count} orphan vertices")

    return errors

if __name__ == "__main__":
    from gremlin_python.process.graph_traversal import __
    conn = DriverRemoteConnection("ws://localhost:8182/gremlin", "g")
    g = Graph().traversal().withRemote(conn)
    errors = validate(g)
    print("VALID" if not errors else "\n".join(errors))
    conn.close()
