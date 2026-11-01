---
name: PulsePilot
description: A guided webcam measurement workspace for estimating pulse and reviewing session evidence.
colors:
  primary: "#26755f"
  forest: "#173f35"
  canvas: "#f0f7f3"
  surface: "#ffffff"
  ink: "#263f39"
  muted: "#536e66"
  line: "#cfe3da"
  nav-highlight: "#9fd8bf"
  accepted-series: "#168286"
  preliminary-series: "#a36614"
  waveform: "#326c68"
  positive-status: "#256b58"
  simulation-status: "#75612c"
typography:
  display:
    fontFamily: "Manrope, Arial, sans-serif"
    fontSize: "64px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Manrope, Arial, sans-serif"
    fontSize: "36px"
    fontWeight: 750
    lineHeight: 1.2
    letterSpacing: "-0.035em"
  title:
    fontFamily: "Manrope, Arial, sans-serif"
    fontSize: "24px"
    lineHeight: 1.4
    letterSpacing: "-0.025em"
  body:
    fontFamily: "Manrope, Arial, sans-serif"
    fontSize: "14px"
    lineHeight: 1.7
  label:
    fontFamily: "Manrope, Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.5
  button:
    fontFamily: "Manrope, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 700
    lineHeight: 1.7
  nav:
    fontFamily: "Manrope, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.7
  field:
    fontFamily: "Manrope, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.7
rounded:
  xs: "4px"
  sm: "6px"
  md: "8px"
  lg: "12px"
spacing:
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  2xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    typography: "{typography.button}"
    rounded: "{rounded.sm}"
    padding: "11px 18px"
    height: "44px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "#42665b"
    typography: "{typography.button}"
    rounded: "{rounded.sm}"
    padding: "11px 18px"
    height: "44px"
  card-surface:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "24px"
  select-field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.field}"
    rounded: "{rounded.sm}"
    padding: "10px"
    height: "46px"
  navigation-active:
    backgroundColor: "transparent"
    textColor: "{colors.surface}"
    typography: "{typography.nav}"
    padding: "3px 0 0"
    height: "84px"
  camera-shell:
    backgroundColor: "{colors.forest}"
    textColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    padding: "18px 22px"
---

# Design System: PulsePilot

## Overview

**Creative North Star: "The Steady Signal Workspace"**

PulsePilot reads as a calm measurement workspace. Forest green anchors navigation and the camera area; the pale mint canvas and white surfaces keep measurements legible. Green marks primary actions, while mint highlights active navigation and face-alignment brackets. Fine rules organize supporting evidence without adding visual weight.

At wide widths, the camera and its controls lead on the left while heart rate, coaching, and setup evidence sit on the right. The layout stacks as space narrows. Manrope, balanced headings, compact labels, and tabular numerals keep the experience familiar and readable. Measurement and chart states remain explicit, including empty and preliminary data.

**Key Characteristics:**
- Forest-green navigation and camera surfaces.
- Pale mint canvas with white, lightly bordered measurement surfaces.
- Green action cues and mint face-alignment brackets.
- Teal and amber chart colors retain their data meanings.

## Colors

The palette shares green action, text, and surface roles across measurement, setup, reports, and the explainer; chart colors remain semantic and local to the data they describe.

### Primary
- **Pulse Green**: Primary buttons, action icons, selected duration, and small interactive accents.
- **Soft Mint**: Active navigation underline and camera alignment brackets.

### Neutral
- **Forest Green**: Horizontal navigation and the camera header.
- **Mint Canvas**: Main application background.
- **White Surface**: Measurement cards, dialogs, and controls.
- **Deep Ink**: Headings and primary text.
- **Muted Green**: Supporting copy and secondary values.
- **Sage Rule**: Fine borders and dividers.

**The Semantic Series Rule.** Accepted heart-rate estimates stay teal; preliminary estimates stay amber and dashed. The normalized waveform keeps its separate teal trace. The face heatmap's red-to-yellow scale represents model attention, not blood flow.

Positive completion and improved-outcome states use a dark green; simulated data uses muted ochre on a pale cream banner.

## Typography

**Display Font:** Manrope (with Arial and sans-serif fallbacks)  
**Body Font:** Manrope (with Arial and sans-serif fallbacks)  
**Label/Mono Font:** Manrope; measurements use tabular numerals.

**Character:** Rounded, open letterforms give headings a quiet confidence. Compact labels and aligned figures keep the workspace practical rather than editorial.

### Hierarchy
- **Display** (600, 64px, 1.2 line-height): Large heart-rate figures in measurement and report summaries; use tabular numerals.
- **Headline** (750, 36px, 1.2 line-height): Main page and report headings.
- **Title** (regular, 24px, 1.4 line-height): Section and supporting headings.
- **Body** (regular, 14px, 1.7 line-height): Explanatory copy; longer report statements cap at 75ch.
- **Label** (600, 12px, 1.5 line-height): Statuses, chart context, and compact labels; buttons use a 700, 13px control weight.

**The Tabular Reading Rule.** Use tabular numerals for heart-rate values, durations, and report statistics so changing measurements stay aligned.

## Layout

The main workspace is centered at a maximum width of 1384px with 32px desktop side padding. The measurement view uses a flexible camera column, a 340px evidence column, and a 28px gap; between 1100px and 800px, the evidence column becomes 300px and the gap 24px. At 800px and below, the measurement columns stack and navigation takes its own row. At 520px and below, side padding reduces to 20px, controls stack, and report summaries use a two-column grid. A 1600px wide-screen rule increases top spacing and camera height.

Spacing clusters around 8px, 12px, 16px, 24px, and 32px. Thin horizontal rules group waveforms, conditions, and report sections.

**The Responsive Stack Rule.** Preserve the camera-first, evidence-second order when the two-column workspace collapses to one column at 800px.

## Elevation & Depth

The resting interface is flat: pale mint canvas, white surfaces, and thin borders establish depth through tone and grouping. A diffuse shadow is reserved for the consent/setup dialog. The forest-green camera area provides a distinct working surface; it does not use a raised-card shadow.

### Shadow Vocabulary
- **Setup dialog** (`0 24px 90px #102e2740`): Separates the active consent and setup dialog from its backdrop.

## Shapes

Buttons, selectors, and compact status labels use gently rounded corners (6px); the heatmap control uses a more rounded edge (8px). Measurement and report cards use a consistent 12px radius. Borders stay thin, while the camera shell's top heading and bottom control tray connect into a single frame. The face guide uses a dashed oval with four mint alignment brackets.

## Components

### Buttons
- **Shape:** Gently rounded corners (6px).
- **Primary:** Green fill, white text, bold 13px label, 11px 18px padding, and 44px minimum height; hover deepens the green.
- **Secondary:** White fill, pale border, muted green text, and the same geometry as the primary button.
- **Hover / Focus:** Hover adjusts fill or border. Keyboard focus uses a 3px green outline with a 4px offset; pressed buttons move down 1px. Disabled controls lower opacity.

### Cards / Containers
- **Corner Style:** 12px on measurement and report cards.
- **Background:** White over the warm canvas.
- **Shadow Strategy:** Flat at rest; the setup dialog is the only raised surface.
- **Border:** 1px cool-gray rule.
- **Internal Padding:** 24px on desktop; report panels tighten to 20px and the heart-rate card to 22px on narrow screens.

### Inputs / Fields
- **Style:** White select field, 1px gray stroke, 6px radius, 10px padding, and 46px minimum height.
- **Focus:** 3px green outline with 4px offset, matching buttons and links.
- **Selection:** Duration options indicate selection through green border and a pale mint fill.

### Navigation
- **Style:** Horizontal forest-green header with white brand, muted labels, and 28px desktop gaps.
- **Active:** White label with a 3px soft-mint underline; the current page is also exposed with `aria-current`.
- **Mobile:** Navigation wraps beneath the brand; labels remain visible as the viewport narrows.

### Camera Alignment Guide
The camera area has a forest-green heading and capture field. Before a session, an original portrait with subtle facial landmarks fills the preview; copy sits alongside it on desktop and below the face on mobile. The visible “Illustrative preview” label and “Camera off” badge distinguish this image from a live measurement. The image disappears while connecting, measuring, or finishing. The connecting and simulation states retain the dashed oval and mint alignment brackets. Guide, live reading, heatmap, and waveform colors retain their current state and data meaning. Image provenance and the full generation prompt live in `public/images/README.md`.

## Do's and Don'ts

### Do:
- **Do** keep the primary action green and the app canvas pale mint.
- **Do** use white, lightly bordered surfaces for measurements and report evidence.
- **Do** keep accepted and preliminary heart-rate series distinguishable by both color and line treatment.
- **Do** leave unavailable readings empty and preserve the visible measurement state.

### Don't:
- **Don't** style a preliminary estimate as an accepted measurement.
- **Don't** present the FacePhys heatmap as a blood-flow or heart-rate visualization; it shows model attention.
- **Don't** fill empty charts or readings with invented values.

## How it works

The explainer opens with a two-column hero: a 38–56px Manrope heading, a short introduction, and a forest-green camera-to-waveform illustration explicitly labeled as an illustration. A visible section navigation links to measurement, AI guidance, the FacePhys model, and limitations. The measurement introduction pairs the sensing explanation with three ordered steps: capture, improve, and review.

Section headings occupy the narrower left column and introductions sit in the wider right column. Technical diagrams span both columns, using open flow nodes with mint rules and directional arrows instead of nested cards. Measurement and event-driven guidance remain separate. Three agent descriptions sit in equal columns on desktop, with their validation and fallback explanation beneath. The FacePhys diagram retains its dark forest surface and distinguishes waveform extraction from PulsePilot's heart-rate and quality processing. Paper and pinned implementation links follow the model explanation.

Body copy uses 16px Manrope with 1.7–1.75 line height; diagram text uses 14px and source notes use 13px. At 800px and below, technical flows and agent descriptions stack. At 520px and below, the hero, section introductions, model explanation, and final call to action stack. All technical details and limitations remain visible. A closing call to action returns to the measurement workspace.

## Session reports

Reports use a centered 1120px reading width and a mint visual treatment inspired by the supplied FacePhys report. The shared colors are deep green ink `#263f39`, muted green `#536e66`, mint `#d9f0e9`, pale sage `#e5f3e5`, translucent white surfaces, and green actions `#26755f`. The workspace, dialogs, navigation, and report list use this same green family; forest `#173f35` anchors dark surfaces and mint `#9fd8bf` highlights them. Manrope remains the typeface, with large tabular measurements and compact supporting labels.

The session title and date lead into an overview: a circular frame around the average estimated heart rate on the left and a two-by-two grid of supporting measurements on the right. The complete, decorative tick ring does not encode a score, quality percentage, target, or normal range. It becomes muted when no accepted heart rate is available. At 800px and below, the overview stacks with the ring first; metric cards retain two columns, including on narrow phones.

Health Insights follow the overview, then recording takeaways, timelines, measurement quality, and capture diagnostics. Each section retains a heading and short supporting text above a white, lightly bordered content panel. Panels use 20px corners, with 14–16px corners for the smaller metric and insight cards. Soft shadows and a mint-to-sage background follow the visual reference. “What this means” and “What to do next” sit side by side on desktop and stack below 800px.

Accepted and preliminary chart series retain their teal and dashed amber meanings, original values, and gaps. All main sections and safety limitations remain visible; only statement sources and chart explanations use disclosures. Evidence stays attached to its statement. Unavailable values remain dashes, and simulation keeps its explicit banner. The report uses existing PulsePilot metrics; the reference’s health grades, psychological scores, and account history are not part of this visual redesign. Print uses white surfaces, visible measurement sections, and simplified spacing without the toolbar or primary action.
