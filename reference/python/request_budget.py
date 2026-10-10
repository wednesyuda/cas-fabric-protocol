"""End-to-end request budgets; timeout never implies provider cancellation."""
import math
import time
from contextvars import ContextVar

request_deadline = ContextVar("request_deadline", default=None)


def deadline_for(payload, timeout):
    supplied = payload.get("expires_at_ms")
    if supplied is not None:
        if isinstance(supplied, bool) or not isinstance(supplied, (int, float)) or not math.isfinite(supplied):
            raise ValueError("expires_at_ms must be a finite timestamp")
        supplied = supplied / 1000
    values = [time.time() + timeout, supplied, request_deadline.get()]
    return min(value for value in values if value is not None)


def remaining(default=120):
    deadline = request_deadline.get()
    budget = default if deadline is None else min(default, deadline - time.time())
    if budget <= 0:
        raise TimeoutError("request expired before execution")
    return budget
