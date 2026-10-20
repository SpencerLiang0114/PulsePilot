# Web experience and design contract

## Visual direction

A calm camera studio, with the face-positioning frame as the defining visual element. White workspace `#ffffff`, cool canvas `#f5f7fa`, navy text `#162b40`, muted slate `#64768a`, teal `#167c80`, and pale teal `#e6f3f0`. Amber `#a96a18` is reserved for an action the user can take. Use Manrope for both interface and display, with tabular numerals for timing and measurements.

The desktop layout has a quiet narrow navigation rail, a wide camera canvas, and an adjacent coach/measurement column. Under the camera, show the pulse trace and quality breakdown. Keep the capture area dominant; avoid an unrelated marketing hero or a wall of identical statistic cards.

```text
Navigation | Title / service status / help
           | Camera and face guide      | Coach and current heart rate
           | Session controls           | Conditions
           | Pulse waveform / quality / progress
```

On mobile the camera comes first, then the action and coach, with measurement charts below. Report and session-history views use the same shell. This design is specific to an active sensing task: the face guide, readiness checks, and uncertainty states occupy the center instead of decorative imagery.

## Journey

1. Start: choose live camera, a user-selected video recording, or an explicitly labeled synthetic scenario. Select duration and consent to frame processing; Meta summary sharing is separately optional.
2. Initializing: connect, warm FacePhys, request camera after consent, and show actionable errors for denied permission, missing camera, busy/unavailable service, or insecure context.
3. Measuring: show preview, face region, one actionable instruction, signal collection progress, elapsed time, and waveform. BPM stays blank until valid.
4. Feedback: show observation window and measured before/after periodicity changes. “Inconclusive” is a normal outcome.
5. Finish: stop camera tracks immediately. Show four report sections, numerical trends, quality history, intervention records, uncertainty, and actual analyst provenance.
6. Review: in-memory history, restart, JSON download, and printable report. Refresh clears history.

## Reliability states

Idle → Initializing → Adjust your position / Measuring → Signal stable / Low confidence → Measurement complete.

State and wording derive from quality and model readiness, never from a decorative timer alone. An unavailable AI service uses clearly attributed deterministic guidance and analysis. Simulation is labeled throughout camera, metrics, report, history, and export, and cannot be mistaken for a real measurement.

## Interaction requirements

Keyboard-visible focus, semantic buttons and headings, reduced-motion support, readable chart alternatives, real error/retry controls, and no stale BPM after face loss/disconnection. Finishing, restarting, changing source, and navigating away stop capture. Extend adds thirty seconds, capped at three minutes. No audio or account requirement.
