
import json
from pathlib import Path
from gremlin_python.process.graph_traversal import __
from gremlin_python.structure.graph import Graph
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from normalizer import load_json, unwrap, safe_key

SCHEMA = json.loads(Path(__file__).resolve().parents[1].joinpath("config/schema.json").read_text())

def upsert_vertex(g, label, key_value, props):
    vid = safe_key(label, key_value)
    t = g.V().has("graph_id", vid)
    if t.hasNext():
        v = t.next()
    else:
        v = g.addV(label).property("graph_id", vid).next()

    for k, val in props.items():
        if val is not None and k not in ("graph_id",):
            g.V(v).property(k, val).iterate()
    return v

def vertex_id(g, label, key_value):
    if key_value is None:
        return None
    vid = safe_key(label, key_value)
    v = g.V().has("graph_id", vid)
    return v.next() if v.hasNext() else None

def upsert_edge(g, edge_label, from_v, to_v, props=None):
    existing = g.V(from_v).outE(edge_label).where(__.inV().is_(to_v))
    if existing.hasNext():
        e = existing.next()
    else:
        e = g.V(from_v).addE(edge_label).to(to_v).next()
    for k, val in (props or {}).items():
        if val is not None:
            g.E(e).property(k, val).iterate()
    return e

def add_employee_from_user(g, row):
    props = {k: row.get(k) for k in SCHEMA["entities"]["Employee"]["properties"]}
    props["userId"] = str(row["userId"])
    return upsert_vertex(g, "Employee", props["userId"], props)

def add_personal(g, row):
    key = f'{row["personIdExternal"]}|{row.get("startDate","")}'
    props = {k: row.get(k) for k in SCHEMA["entities"]["PersonalInfo"]["properties"]}
    props["personIdExternal"] = str(row["personIdExternal"])
    return upsert_vertex(g, "PersonalInfo", key, props)

def add_time(g, row):
    key = row.get("externalCode")
    if not key:
        # Some EmployeeTime responses use only selected fields.
        key = f'{row.get("userId","unknown")}|{row.get("startDate","")}|{row.get("endDate","")}'
    props = {k: row.get(k) for k in SCHEMA["entities"]["EmployeeTime"]["properties"]}
    props["externalCode"] = key
    return upsert_vertex(g, "EmployeeTime", key, props)

def add_holiday(g, row):
    key = row.get("externalCode")
    if not key:
        return None
    props = {k: row.get(k) for k in SCHEMA["entities"]["Holiday"]["properties"]}
    return upsert_vertex(g, "Holiday", key, props)

def add_calendar(g, calendar_code):
    if not calendar_code:
        return None
    return upsert_vertex(g, "HolidayCalendar", calendar_code, {"calendarCode": calendar_code})

def add_time_account(g, row):
    ta = row.get("timeAccount", {})
    bal = row.get("balances", {})
    code = ta.get("externalCode")
    if not code:
        return None
    props = {
        "timeAccountKey": code,
        "accountTypeCode": (ta.get("timeAccountType") or {}).get("externalCode"),
        "accountTypeName": (ta.get("timeAccountType") or {}).get("externalName"),
        "unit": (ta.get("timeAccountType") or {}).get("unit"),
        "bookableStartDate": ta.get("bookableStartDate"),
        "bookableEndDate": ta.get("bookableEndDate"),
    }
    for name in ("available","accrued","earned","paidOut","planned","taken"):
        props[name] = (bal.get(name) or {}).get("value")
    return upsert_vertex(g, "TimeAccountBalance", code, props)

def connect_employee(g, user_id, label, key):
    ev = vertex_id(g, "Employee", str(user_id))
    tv = vertex_id(g, label, key)
    if ev and tv:
        rel = {
            "PersonalInfo":"HAS_PERSONAL_INFO",
            "EmployeeTime":"HAS_TIME_RECORD",
            "Compensation":"HAS_COMPENSATION",
            "TimeAccountBalance":"HAS_TIME_BALANCE"
        }.get(label)
        if rel:
            upsert_edge(g, rel, ev, tv)

def ingest_fixtures(g, fixtures_dir):
    f = Path(fixtures_dir)

    # User -> Employee
    rows = unwrap(load_json(f/"response get user(1)"))
    for r in rows:
        add_employee_from_user(g, r)

    # PersonalInfo
    rows = unwrap(load_json(f/"PEOPLE INFO API(1)"))
    for r in rows:
        v = add_personal(g, r)
        if v and r.get("personIdExternal"):
            # personIdExternal is the cross-source identity in this POC.
            ev = vertex_id(g, "Employee", str(r["personIdExternal"]))
            if ev:
                upsert_edge(g, "HAS_PERSONAL_INFO", ev, v)

    # EmployeeTime
    rows = unwrap(load_json(f/"leave status of user get api(1)"))
    for r in rows:
        v = add_time(g, r)
        if v and r.get("userId"):
            connect_employee(g, r["userId"], "EmployeeTime", r.get("externalCode"))

    # Large WFREQUEST response is also EmployeeTime; enrich/upsert same nodes.
    rows = unwrap(load_json(f/"WFR REQUEST GET API(1)"))
    for r in rows:
        v = add_time(g, r)
        if v and r.get("userId"):
            connect_employee(g, r["userId"], "EmployeeTime", r.get("externalCode"))

    # Holiday
    rows = unwrap(load_json(f/"get holidays response(1)"))
    for r in rows:
        add_holiday(g, r)

    # Time account balances
    rows = unwrap(load_json(f/"just leave status get of user(1)"))
    for r in rows:
        add_time_account(g, r)

def main():
    # Point this at a running Gremlin Server.
    conn = DriverRemoteConnection("ws://localhost:8182/gremlin", "g")
    g = Graph().traversal().withRemote(conn)
    ingest_fixtures(g, Path(__file__).resolve().parents[1] / "fixtures")
    print("vertices:", g.V().count().next())
    print("edges:", g.E().count().next())
    conn.close()

if __name__ == "__main__":
    main()
