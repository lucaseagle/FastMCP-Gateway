import json
import logging

from opentelemetry import metrics, trace
from opentelemetry._logs import get_logger_provider

from fastmcp_gateway.telemetry import configure


def test_telemetry_is_opt_in_and_audit_logger_is_isolated(capsys):
    audit = logging.getLogger("gateway.audit")
    previous = list(audit.handlers)
    try:
        configure(None)
        audit.info(json.dumps({"event": "test", "outcome": "ok"}))
        assert '"outcome": "ok"' in capsys.readouterr().err
        assert audit.propagate is False
    finally:
        for handler in audit.handlers:
            if handler not in previous:
                handler.close()
        audit.handlers = previous


def test_otlp_exports_all_three_signals_without_payloads(monkeypatch):
    import fastmcp_gateway.telemetry as telemetry

    exported = {"traces": [], "metrics": [], "logs": []}

    class Exporter:
        _preferred_temporality = None
        _preferred_aggregation = None

        def __init__(self, signal):
            self.signal = signal

        def export(self, data, **kwargs):
            exported[self.signal].append(data)

        def shutdown(self, **kwargs):
            pass

        def force_flush(self, **kwargs):
            return True

    for name, signal in [
        ("OTLPSpanExporter", "traces"),
        ("OTLPMetricExporter", "metrics"),
        ("OTLPLogExporter", "logs"),
    ]:
        monkeypatch.setattr(telemetry, name, lambda endpoint, signal=signal: Exporter(signal))
    telemetry.configure("http://collector.invalid:4318")
    with trace.get_tracer("gateway-test").start_as_current_span("gateway.execute"):
        pass
    metrics.get_meter("gateway-test").create_counter("gateway.test").add(1)
    logging.getLogger("gateway.audit").info('{"event":"test","outcome":"ok"}')
    assert trace.get_tracer_provider().force_flush()
    assert metrics.get_meter_provider().force_flush()
    assert get_logger_provider().force_flush()
    assert all(exported.values())
