---
version: alpha
colors:
  canvas: "#f3f6f8"
  surface: "#ffffff"
  ink: "#172d38"
  muted: "#526773"
  primary: "#176b58"
  primarySoft: "#e8f4ee"
  border: "#d9e2e7"
  accent: "#b06426"
typography:
  display:
    fontFamily: "Segoe UI Variable Display, Segoe UI, sans-serif"
    fontSize: "38px"
    lineHeight: "1.15"
  body:
    fontFamily: "Segoe UI Variable Text, Segoe UI, Arial, sans-serif"
    fontSize: "15px"
    lineHeight: "1.6"
  utility:
    fontFamily: "Cascadia Code, Consolas, monospace"
    fontSize: "12px"
    lineHeight: "1.5"
rounded:
  control: "10px"
  panel: "18px"
spacing:
  unit: "4px"
components:
  button:
    minHeight: "44px"
  field:
    minHeight: "46px"
---

## Overview
Own is a calm teaching desk for people who know their business but do not know machine learning. Product register. The visual reference is a well-organized lesson notebook: real examples, visible review marks and a progression from teaching to checks. Avoid GPU dashboards, glowing brains, sales-page heroes and invented accuracy statistics.

The signature is a small green learning path on the home screen and numbered, plain-language steps within a job. Boldness belongs in the overlapping O mark and generous task-focused titles; controls remain familiar.

## Colors
Runtime ownership is `web/styles.css :root`. The frontmatter colors map one-to-one to `--canvas`, `--surface`, `--ink`, `--muted`, `--primary`, `--primary-soft`, `--border`, `--accent`. Scrollbar roles use the same muted/border tokens. Error #a23832 and error surface #fff2f0 are semantic additions.

## Typography
Use local system fonts; no downloads. Titles use the display stack, body the body stack, IDs/commands the utility stack. English UI; arbitrary Unicode in business content. Browser-local date/time formatting.

## Layout
236px left workspace rail, max 1140px content, generous 32px gaps. Main content scrolls naturally; do not clip forms to viewport height. At 850px, use a compact horizontal navigation and one content column. At 520px, reduce gutters to 18px; keep every action reachable.

## Elevation & Depth
Thin borders on static panels; subtle shadow only on dialogs and the welcome composition. No ambient glow, gradients or glass effects.

## Shapes
10px controls, 18px panels, round status dots. A single softly rounded path illustration expresses teaching, testing and control.

## Components
Shared `button`, `field`, `panel`, `notice`, `empty`, `dialog` and `toast` styles. SVG icons use one 1.7px stroke. Native select popup deliberately follows Windows/browser conventions. Native dialog supplies modal semantics and focus isolation.

## Do's and Don'ts
Show real saved counts. Say "Not checked" before checks run. Say "Teaching examples" for prompt-based customization; reserve "trained model" for completed, verified weight updates. Local starter training is available; cloud GPU training and managed deployment remain future milestones. Show errors beside retained input. Respect reduced motion and visible focus. Use text badges as well as colors. No native alert/confirm/prompt.

## Step 2 training
The Train it tab extends the teaching desk: three real stages, reviewed lessons → real learning steps → paired before/after answers. Reuse the established panel, field, native dialog, progress, badge and notification owners. Do not expose a GPU console or optimizer form to ordinary users. Technical evidence lives under Training details. No new visual tokens. A completed model gets a human comparison, never an invented accuracy score. At narrow widths, comparison columns stack in before/after reading order; all actions remain reachable.
