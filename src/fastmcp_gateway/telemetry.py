"""Opt-in OTLP traces, metrics and sanitized audit logs. No content export."""

import atexit
import logging

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def configure(endpoint: str | None) -> None:
    audit = logging.getLogger("gateway.audit")
    audit.setLevel(logging.INFO)
    audit.propagate = False
    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter("%(message)s"))
    audit.addHandler(stream)
    # Library error logs can include untrusted input; only our bounded audit events are exported.
    logging.getLogger("fastmcp").setLevel(logging.CRITICAL)
    logging.getLogger("mcp").setLevel(logging.CRITICAL)
    if endpoint is None:
        return
    resource = Resource.create({"service.name": "fastmcp-gateway", "service.version": "0.1.0"})
    endpoint = endpoint.rstrip("/")
    traces = TracerProvider(resource=resource)
    traces.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"))
    )
    trace.set_tracer_provider(traces)
    metric_provider = MeterProvider(
        resource=resource,
        metric_readers=[
            PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics"))
        ],
    )
    metrics.set_meter_provider(metric_provider)
    logs = LoggerProvider(resource=resource)
    logs.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{endpoint}/v1/logs"))
    )
    set_logger_provider(logs)
    audit.addHandler(LoggingHandler(level=logging.INFO, logger_provider=logs))
    for provider in (traces, metric_provider, logs):
        atexit.register(provider.shutdown)
