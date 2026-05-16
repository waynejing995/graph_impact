# Base Workbench Geometry Prompt

Use this geometry block in every page-level anchor prompt. Page prompts may change content, active navigation, tables, and graph details, but they must not move the shell.

```text
Hard geometry constraints: one 2048 x 1280 desktop app screenshot. Full-bleed app viewport, no browser chrome and no floating outer frame. Top bar is fixed at x=0, y=0, width=2048, height=72, with its bottom divider at y=72. Left rail is fixed at x=0, y=72, width=288, height=1208. Main grid starts at x=288, y=72, width=1760, height=1208. Center content origin is x=312, y=96 with 24px inner padding. Right inspector is fixed at x=1536, y=72, width=488, height=1208, with 24px inner padding and a 24px right app margin. Keep these chrome coordinates identical across every route. Do not widen, shrink, shift, center, or reframe the top bar, left rail, center workspace, or right inspector to fit page-specific content.
```
