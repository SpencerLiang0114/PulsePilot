# PulsePilot

<!-- impeccable:product-schema 1 -->

## Platform

web

## Product Purpose

PulsePilot is a webcam heart-rate research application. It guides a measurement, shows signal quality and coaching, and produces evidence-grounded reports. Repository source: README.md.

## Capabilities and Constraints

- Live camera, uploaded recording, and explicitly labeled synthetic simulation.
- Explicit frame-processing consent and separate optional Muse Spark consents.
- Real inference runs in the existing Python service; this redesign changes presentation only.
- Reports live in page memory and support JSON export and printing.
- Preserve unavailable, initializing, active, stale, insufficient-signal, and completed states. Never fabricate a reading or imply clinical validation.

## Users

Specific audience prioritization is undecided. The user delegated frontend design decisions; infer task priorities from the existing measurement workflow.

## Brand Commitments

Keep the PulsePilot name, product facts, and functions. Apply Impeccable to redesign the frontend.
