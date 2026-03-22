"""
Transparent HTTP reverse proxy for the Snowflake Emulator.

Fixes emulator compatibility issues with snowflake-connector-python 3.x:
1. Decompresses gzip-encoded request bodies.
2. Injects missing session parameters with correct Python types.
3. Injects missing column metadata fields (length, precision, scale) in query responses.
4. Injects a DDL rowtype/rowSet when the emulator omits them (DDL statements).
5. Rewrites SQL to strip TRANSIENT TABLE, three-part qualified names, and SQL comments.
6. Synthesises SELECT results for VALUES table expressions the emulator silently drops.

Note on SQL comments: the emulator's DuckDB backend fails to execute any SQL that starts
with a comment (/* */ or --). All SQL comments are stripped before forwarding.
"""
import gzip
import http.server
import json
import re
import urllib.request
import urllib.error


UPSTREAM = "http://snowflake-emulator:8080"

# Session parameters the connector requires but the emulator doesn't return.
_REQUIRED_PARAMS: dict[str, object] = {
    "CLIENT_PREFETCH_THREADS": 4,
    "CLIENT_RESULT_CHUNK_SIZE": 160,
    "CLIENT_SESSION_KEEP_ALIVE_HEARTBEAT_FREQUENCY": 3600,
    "CLIENT_SESSION_KEEP_ALIVE": False,
    "AUTOCOMMIT": True,
    "BINARY_INPUT_FORMAT": "HEX",
    "BINARY_OUTPUT_FORMAT": "HEX",
    "DATE_OUTPUT_FORMAT": "YYYY-MM-DD",
    "TIME_OUTPUT_FORMAT": "HH24:MI:SS",
    "TIMESTAMP_LTZ_OUTPUT_FORMAT": "",
    "TIMESTAMP_NTZ_OUTPUT_FORMAT": "YYYY-MM-DD HH24:MI:SS.FF9",
    "TIMESTAMP_TZ_OUTPUT_FORMAT": "",
    "TIMEZONE": "UTC",
    "TRANSACTION_ABORT_ON_ERROR": False,
}

# Integer params that the emulator returns as strings
_INT_PARAM_NAMES = {"CLIENT_PREFETCH_THREADS", "CLIENT_RESULT_CHUNK_SIZE",
                    "CLIENT_SESSION_KEEP_ALIVE_HEARTBEAT_FREQUENCY"}

# Boolean params returned as strings
_BOOL_PARAM_NAMES = {"CLIENT_SESSION_KEEP_ALIVE", "AUTOCOMMIT",
                     "TRANSACTION_ABORT_ON_ERROR"}


def _fix_login_response(body_bytes: bytes) -> bytes:
    """Ensure all required session parameters are present with correct types."""
    try:
        obj = json.loads(body_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return body_bytes

    data = obj.get("data")
    if not isinstance(data, dict):
        return body_bytes

    params: list[dict] = data.setdefault("parameters", [])
    existing = {p["name"]: i for i, p in enumerate(params)}

    for name, default_value in _REQUIRED_PARAMS.items():
        if name in existing:
            raw = params[existing[name]].get("value")
            if name in _INT_PARAM_NAMES:
                try:
                    params[existing[name]]["value"] = int(raw)
                except (TypeError, ValueError):
                    params[existing[name]]["value"] = default_value
            elif name in _BOOL_PARAM_NAMES:
                if isinstance(raw, str):
                    params[existing[name]]["value"] = raw.lower() == "true"
        else:
            params.append({"name": name, "value": default_value})

    return json.dumps(obj).encode()


_DDL_STATUS_COL = {
    "name": "status",
    "type": "text",
    "nullable": False,
    "length": 16777216,
    "byteLength": None,
    "precision": None,
    "scale": None,
    "extTypeName": "",
}

_TEXT_COL_TEMPLATE = {
    "type": "text",
    "nullable": True,
    "length": 16777216,
    "byteLength": None,
    "precision": None,
    "scale": None,
    "extTypeName": "",
}

# Matches: from (values (row), ...) as alias(col1, col2, ...)
_VALUES_RE = re.compile(
    r"from\s*\(values\s*((?:\([^)]*\)\s*,?\s*)+)\)\s*as\s+\w+\s*\(([^)]+)\)",
    re.IGNORECASE | re.DOTALL,
)


def _parse_values_query(sql: str):
    """Return (column_names, rows) if sql is a SELECT...FROM (values...) query.

    Returns None if the SQL doesn't match the pattern.
    """
    sql_stripped = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL).strip()
    if not sql_stripped.lower().startswith("select"):
        return None

    m = _VALUES_RE.search(sql_stripped)
    if not m:
        return None

    values_block = m.group(1)
    col_names_raw = m.group(2)
    column_names = [c.strip() for c in col_names_raw.split(",")]

    row_re = re.compile(r"\(([^)]+)\)")
    rows = []
    for row_match in row_re.finditer(values_block):
        raw_items = row_match.group(1).split(",")
        row = []
        for item in raw_items:
            item = item.strip()
            if item.startswith("'") and item.endswith("'"):
                item = item[1:-1]
            row.append(item)
        rows.append(row)

    return column_names, rows


def _rewrite_sql_body(body: bytes) -> bytes:
    """Rewrite SQL in a query-request body to be emulator-compatible.

    - Strips SQL comments (emulator fails on any /* */ or -- comments)
    - Strips three-part qualified names: BANK_DB.RAW.tablename → tablename
    - Removes TRANSIENT keyword from CREATE TABLE statements
    """
    try:
        obj = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return body

    sql = obj.get("sqlText", "")
    if not sql:
        return body

    # Strip SQL comments — the emulator (DuckDB backend) fails on any comment prefix.
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = sql.strip()

    sql = re.sub(r"\bBANK_DB\.RAW\.", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bTRANSIENT\s+TABLE\b", "TABLE", sql, flags=re.IGNORECASE)

    if sql == obj.get("sqlText", ""):
        return body  # no change

    obj["sqlText"] = sql
    return json.dumps(obj).encode()


def _fix_query_response(body_bytes: bytes, sql: str = "") -> bytes:
    """Inject missing column metadata fields that connector 3.x requires.

    Also synthesises a DDL-style rowtype/rowSet when the emulator omits them
    (e.g. for CREATE / DROP / ALTER statements).

    Intercepts SELECT...FROM (values...) queries that the emulator silently
    drops and injects the values directly.
    """
    try:
        obj = json.loads(body_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return body_bytes

    data = obj.get("data")
    if not isinstance(data, dict):
        return body_bytes

    rowtype = data.get("rowtype")
    rowset = data.get("rowset")

    if not isinstance(rowtype, list):
        # No rowtype — check if this was a SELECT VALUES query the emulator dropped.
        if sql:
            parsed = _parse_values_query(sql)
            if parsed is not None:
                column_names, rows = parsed
                data["rowtype"] = [
                    dict(_TEXT_COL_TEMPLATE, name=col) for col in column_names
                ]
                data["rowset"] = rows
                data["total"] = len(rows)
                data["returned"] = len(rows)
                return json.dumps(obj).encode()

        # DDL or other statement that returned no rowtype — synthesise one.
        data["rowtype"] = [_DDL_STATUS_COL]
        data.setdefault("rowset", [["Statement executed successfully."]])
        data.setdefault("total", 1)
        data.setdefault("returned", 1)
        return json.dumps(obj).encode()

    # DDL responses sometimes return rowtype=[] with no rowset — synthesise.
    # Use `is None` not `not` so that rowset=[] (empty SELECT) is preserved.
    if not rowtype and rowset is None:
        data["rowtype"] = [_DDL_STATUS_COL]
        data["rowset"] = [["Statement executed successfully."]]
        data.setdefault("total", 1)
        data.setdefault("returned", 1)
        return json.dumps(obj).encode()

    for col in rowtype:
        col.setdefault("length", None)
        col.setdefault("precision", None)
        col.setdefault("scale", None)
        col.setdefault("nullable", True)
        col.setdefault("byteLength", None)
        col.setdefault("extTypeName", "")
        # Normalize NUMBER → fixed so the connector can find a type converter.
        # Also set scale=0 when null so _FIXED_to_python returns int (not Decimal/str).
        if col.get("type", "").upper() in ("NUMBER", "FIXED"):
            col["type"] = "fixed"
            if col.get("scale") is None:
                col.setdefault("precision", 18)
                col["scale"] = 0

    return json.dumps(obj).encode()


class GunzipProxy(http.server.BaseHTTPRequestHandler):
    def _forward(self, method: str, body: bytes | None = None) -> None:
        forward_headers: dict[str, str] = {
            k: v
            for k, v in self.headers.items()
            if k.lower() not in ("host", "content-encoding", "content-length")
        }

        if body and self.headers.get("Content-Encoding", "").lower() == "gzip":
            body = gzip.decompress(body)

        is_query = "/query-request" in self.path or "/queries/" in self.path

        # Rewrite SQL before sending to emulator.
        if is_query and body:
            body = _rewrite_sql_body(body)

        if body:
            forward_headers["Content-Length"] = str(len(body))

        req = urllib.request.Request(
            UPSTREAM + self.path,
            data=body,
            headers=forward_headers,
            method=method,
        )
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            resp_body = resp.read()
            status = resp.status
            resp_headers = dict(resp.headers)
        except urllib.error.HTTPError as e:
            resp_body = e.read()
            status = e.code
            resp_headers = dict(e.headers)

        if "/login-request" in self.path:
            resp_body = _fix_login_response(resp_body)
            resp_headers["Content-Length"] = str(len(resp_body))
        elif is_query:
            sql = ""
            if body:
                try:
                    sql = json.loads(body).get("sqlText", "")
                except Exception:
                    pass
            resp_body = _fix_query_response(resp_body, sql)
            resp_headers["Content-Length"] = str(len(resp_body))

        self.send_response(status)
        for key, value in resp_headers.items():
            if key.lower() not in ("transfer-encoding", "connection"):
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(resp_body)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        self._forward("POST", self.rfile.read(length))

    def do_GET(self) -> None:
        self._forward("GET")

    def log_message(self, fmt: str, *args: object) -> None:  # noqa: D102
        pass  # suppress access logs


if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", 8081), GunzipProxy)
    print("Snowflake proxy listening on :8081 → forwarding to emulator:8080")
    server.serve_forever()
