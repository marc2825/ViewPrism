"""Compatibility alias for the independent verification harness in ``viewpass-dev/``.

The product package is ``viewprism`` (ViewPrism - Viewport Pass Exporter). The harness was written
against the working name and is kept unchanged on purpose; it imports ``viewpass`` and
``viewpass.capture``. This alias forwards to exactly the same entry points. It is not part of the
extension package (only ``viewprism/`` is built).
"""
from viewprism import register, unregister  # noqa: F401
