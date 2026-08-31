"""The device's only outbound connection: one WebSocket to the gateway.

Rule of thumb from the plan: the device knows exactly one endpoint. Direct
function calls between device and gateway code are forbidden -- migrating to the
VPS must be nothing more than changing GATEWAY_URL.
"""

from __future__ import annotations

# TODO(phase-0): connect, send session_start, stream mic frames, dispatch
# incoming state/transcript/tool_call messages, honour SIMULATED_LATENCY_MS.
