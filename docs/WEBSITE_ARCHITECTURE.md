# StructuralPro Website Architecture

## Positioning
StructuralPro is a complete AEC software ecosystem connecting measurement, estimating, engineering, construction and project intelligence.

Primary message: **30 Products. One AEC Ecosystem.**
Secondary message: **From Drawing to Decision.**

## Site principles
1. StructuralPro is presented as an AEC ecosystem, not a single takeoff application.
2. Takeoff is one entry point in the workflow, not the product definition.
3. Product claims must map to implemented or explicitly planned capabilities.
4. English and Persian are first-class locales.
5. Persian is designed as true RTL, including navigation, cards, tables, controls and data presentation.
6. The visual language is technical, premium and engineering-led.
7. The site should remain usable without JavaScript for core navigation and content discovery.
8. Commercial CTAs must distinguish available, planned and gated product capabilities.
9. Product categories are used to avoid a crowded 30-item wall.
10. Enterprise is the platform-level offer; the other 29 entries are specialized products.

## Primary navigation
- Products
- Solutions
- Industries
- Features
- Resources
- Pricing
- Company
- Support

Primary actions:
- Download / Get Started
- Sign In

## Homepage information architecture
1. Header
2. Hero
3. Ecosystem overview
4. Product categories
5. Solutions by role
6. From Drawing to Decision workflow
7. AEC coverage
8. AI
9. BIM
10. Windows-first desktop
11. Cloud and collaboration
12. Workflow comparison
13. Security and data
14. Resources
15. Final CTA
16. Footer

## Product taxonomy
### Takeoff & Estimating
- StructuralPro Takeoff
- StructuralPro CAD Takeoff
- StructuralPro BIM Takeoff
- StructuralPro BOQ
- StructuralPro Estimating

### Project & Commercial Management
- StructuralPro Technical Office
- StructuralPro Site Supervisor
- StructuralPro Project Controls
- StructuralPro Project Manager
- StructuralPro Cost Control
- StructuralPro Contract & Claims
- StructuralPro Procurement

### BIM, AI & Intelligence
- StructuralPro BIM & Coordination
- StructuralPro AI & AEC Assistant
- StructuralPro Reports & Intelligence
- StructuralPro Price & Cost Intelligence

### Engineering
- StructuralPro Structural Analysis & Design
- StructuralPro Geotechnical
- StructuralPro Architecture
- StructuralPro MEP
- StructuralPro Civil & Site
- StructuralPro Concrete Engineering
- StructuralPro Steel Engineering
- StructuralPro Masonry Engineering
- StructuralPro Timber Engineering
- StructuralPro Composite Structures
- StructuralPro Precast
- StructuralPro Special Structures

### Enterprise
- StructuralPro AEC Enterprise

## Role-based solution routes
- Quantity Surveyor / Estimator
- Technical Office
- Site Supervisor
- Project Controller
- Project Manager
- BIM Manager
- Structural Engineer
- Architect
- MEP Engineer
- Geotechnical Engineer
- Contract / Commercial Team
- Enterprise

## Canonical workflow
Drawing / BIM → Takeoff → BOQ → Estimate → Contract → Procurement → Construction → Progress → Cost Control → Reports → Management Decision

AI and BIM are cross-cutting capabilities across the workflow.

## Locale model
Supported locales:
- en — English / LTR
- fa — فارسی / RTL

Locale must be represented in routing and content data rather than inferred only from CSS.

## Responsive model
- Mobile: 320–767px
- Tablet: 768–1199px
- Desktop: 1200px+
- Large desktop: 1440px+

## Design-token direction
- Technical dark navy base
- Controlled electric-cyan accent
- Neutral surfaces for engineering data
- High-contrast text
- Restrained gradients
- Engineering grid / drawing-line motifs
- Consistent radius and spacing scale
- Motion used to explain relationships, not decorate every element

## Content integrity
Every future product page must distinguish:
- Available capability
- Planned capability
- Integration / dependency
- Commercial availability

No invented screenshots, fake download links, fake customer claims or unsupported security claims.

## Phase 1 completion definition
Phase 1 is complete when:
- the information architecture is canonical;
- the 30-product taxonomy is machine-readable;
- primary navigation is machine-readable;
- English/Persian locale structure exists;
- workflow and role routes are defined;
- responsive breakpoints and design-token direction are documented;
- later UI phases can consume these sources without duplicating product names or navigation labels.
