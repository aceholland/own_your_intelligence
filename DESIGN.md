---
version: alpha
colors:
  canvas: "#efebe1"
  surface: "#f8f5ed"
  rail: "#e4dfd1"
  ink: "#2a2923"
  muted: "#605a4e"
  primary: "#3b4232"
  primarySoft: "#e5e7da"
  border: "#b6af9e"
  accent: "#805037"
typography:
  display:
    fontFamily: "Georgia, Times New Roman, serif"
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
  control: "2px"
  panel: "2px"
spacing:
  unit: "4px"
components:
  button:
    minHeight: "44px"
  field:
    minHeight: "46px"
---

## Overview
Acewyn AI is a teaching desk for people who know their business and want to train an AI in their own words. The workbench draws on an editorial folio. Ivory paper and large serif headings establish the pace, with a ruled grid to make actions and review decisions easy to find.

The signature is the divided overview spread, pairing the workbench's title with an original photograph of a hand correcting a notebook. The numbered stages below it carry the same grid into jobs. Photography stays on the overview and welcome screens. Forms and comparisons use text, space, and rules.

## Colors
Runtime ownership is `web/styles.css :root`. The frontmatter colors map to `--canvas`, `--surface`, `--rail`, `--ink`, `--muted`, `--primary`, `--primary-soft`, `--border`, and `--accent`. Strong rules mark structural divisions and field edges. The olive tone marks active choices and trained answers. Warm warning and error colors always accompany a text label.

## Typography
Use local system fonts. Georgia sets page titles and panel headings, Segoe UI sets controls and body copy, and Cascadia Code sets figure labels, stage numbers, IDs, and commands. English UI with arbitrary Unicode in business content. Dates use the browser’s local time zone.

## Layout
236px left workspace rail, max 1140px content, generous 32px gaps. Main content scrolls naturally; do not clip forms to viewport height. At 850px, use a compact horizontal navigation and one content column. At 520px, reduce gutters to 18px; keep every action reachable.

## Elevation & Depth
Thin rules define static panels and spreads. Shadows indicate floating dialogs and notifications.

## Shapes
Square-edged panels and controls with a 2px corner radius. Round status dots and stage markers keep their own shape.

## Components
Shared `button`, `field`, `panel`, `notice`, `empty`, `dialog` and `toast` styles. SVG icons use one 1.7px stroke. Native select popup deliberately follows Windows/browser conventions. Native dialog supplies modal semantics and focus isolation.

## Do's and Don'ts
Show real saved counts. Say "Not checked" before checks run. Say "Teaching examples" for prompt-based customization; reserve "trained model" for completed, verified weight updates. Local training is verified; the supervised GPU workflow is available with its first actual L4 test pending. Managed GPU deployment remains a future milestone. Show errors beside retained input. Respect reduced motion and visible focus. Use text badges as well as colors. No native alert/confirm/prompt.

## Step 2 training
The Train it tab extends the teaching desk: three real stages, reviewed lessons → real learning steps → paired before/after answers. Reuse the established panel, field, native dialog, progress, badge and notification owners. Do not expose a GPU console or optimizer form to ordinary users. Technical evidence lives under Training details. No new visual tokens. A completed model gets a human comparison, never an invented accuracy score. At narrow widths, comparison columns stack in before/after reading order; all actions remain reachable.

## Stronger-model setup
A child of Train it. Reuse the notebook's three steps: review lessons, train, see what changed. Existing panel, field, native dialog, progress and comparison owners stay canonical. Account details and portable preparation sit in a disclosure; connected owners see the main training action. Billing help says what the card can pay in simple language. Four per-run confirmations start unchecked; display owner confirmation separately from automatic verification. Real steps drive progress, an unconfirmed stop stays visible, and completion requires validated actual weights. No GPU model selection button until hosting works. Keep technical evidence under Training details. No new visual tokens.
