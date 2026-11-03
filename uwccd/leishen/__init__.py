"""Leishen / Thunderobot (Quanta chassis with Leishen ControlCenter 3.x) — experimental, separate module.

These laptops have no Uniwill EC interface. Their firmware takes commands through one WMI data block (RW_GMWMI,
GUID 644C5791-B7B0-4123-A90B-E93876E0DAAD): power mode, fan speeds, temperatures and fan speeds, Windows key lock,
keyboard light. The command layout was read from the firmware's own ACPI methods (WSAA / WQAA) and from how Leishen
ControlCenter 3.0.0.18 uses the block (interoperability analysis); no vendor code is used. See docs/LEISHEN.md.
"""
from .manager import LeishenManager  # noqa: F401
