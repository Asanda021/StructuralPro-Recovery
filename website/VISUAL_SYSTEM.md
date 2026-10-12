# StructuralPro Website — Phase 2 Visual System

## Purpose
A premium, engineering-first visual system for the StructuralPro AEC ecosystem.

## Principles
- Technical before decorative.
- Drawing/BIM/data motifs should explain the product, not become wallpaper.
- Use electric cyan as a controlled interaction/accent color.
- Keep surfaces neutral and dense enough for professional workflows.
- Light and dark themes share the same semantic tokens.
- Persian is a true RTL locale: layout, alignment, navigation, tables and component internals must mirror correctly.

## Components
Core reusable components: Button, Navigation, Card, Product Card, Badge, Input, Table, Data Card, Modal, Tabs, Breadcrumbs, CTA.

Each component must expose semantic states: default, hover, focus-visible, active, disabled, loading, success/warning/error where applicable.

## Motion
120–320ms transitions. Prefer transform/opacity. Respect reduced motion. No perpetual decorative animation.

## Responsive
Mobile 320–767, tablet 768–1199, desktop 1200–1439, large desktop 1440+. Keep a 1280px content max width and use fluid gutters.

## Accessibility
Target WCAG AA contrast, keyboard-visible focus, 44px minimum touch targets, semantic headings, logical tab order, reduced-motion support.

## RTL validation
Persian sample: «از نقشه تا تصمیم — یک اکوسیستم یکپارچه AEC»
Use logical CSS properties such as margin-inline, padding-inline, inset-inline and text-align: start rather than hard-coded left/right values.
