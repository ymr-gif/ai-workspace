from prometheus_client import Counter

FILE_UPLOADS    = Counter("file_uploads_total",    "Files uploaded")
FILE_DELETES    = Counter("file_deletes_total",    "Files deleted")
FILE_CHUNKS     = Counter("file_chunks_total",     "File chunks embedded")
FILE_TOOL_CALLS = Counter("file_tool_calls_total", "File tool calls by name", ["tool"])


def record_upload():          FILE_UPLOADS.inc()
def record_delete():          FILE_DELETES.inc()
def record_chunks(n: int):    FILE_CHUNKS.inc(n)
def record_tool_call(name: str): FILE_TOOL_CALLS.labels(tool=name).inc()
