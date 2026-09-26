"""Source-capture adapters. Captured model output is never classifier truth."""

from .grok import GrokSourceClient, GrokSourceError

__all__ = ["GrokSourceClient", "GrokSourceError"]
