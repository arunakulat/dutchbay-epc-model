# Dutch Bay EPC Design System

**Interactive Financial Modeling Dashboard – Complete Design System Documentation**

---

## 📑 Table of Contents

1. [Overview](#overview)
2. [Design System Files](#design-system-files)
3. [Quick Start](#quick-start)
4. [Color System](#color-system)
5. [Typography](#typography)
6. [Components](#components)
7. [Screens & Layouts](#screens--layouts)
8. [For Developers](#for-developers)
9. [For Designers](#for-designers)
10. [Implementation Guide](#implementation-guide)
11. [Figma Setup](#figma-setup)
12. [Best Practices](#best-practices)

---

## Overview

### What Is This?

A complete, production-ready design system for the **Dutch Bay Wind Project** – a multi-currency project finance application with interactive financial modeling dashboards, scenario analysis, and reporting capabilities.

### Key Features

- ✅ **Mobile-First Design** – iPhone SE & Android phone responsive layouts
- ✅ **Dark Mode Ready** – CSS tokens support light/dark theme switching
- ✅ **Component-Based** – Reusable buttons, cards, inputs, badges, navigation
- ✅ **Financial UI** – Specialized metric cards, charts, tables for finance data
- ✅ **Accessibility** – WCAG 2.1 AA standards, keyboard navigation, focus states
- ✅ **Dev-Friendly** – CSS custom properties, semantic HTML, zero dependencies
- ✅ **Figma-Integrated** – 1-to-1 mapping between design and code

### Project Context

**Dutch Bay EPC** is an Engineering, Procurement, Construction financial model for a wind energy project. The app provides:

- **Dashboard** – Key metrics (NPV, IRR, DSCR), revenue trends, project status
- **Scenarios** – Base case, optimistic, conservative modeling with sensitivity analysis
- **Metrics Detail** – Deep-dive into DSCR, revenue/cost projections
- **Reports** – Financial summaries, annual reports, cash flow forecasts
- **Settings** – Project assumptions, wind resources, tariff rates

---

## Design System Files

### Complete Deliverables

| File | Type | Purpose | Audience |
|------|------|---------|----------|
| **DutchBay_Design_System.css** | CSS | Production-ready design tokens + component styles | Developers |
| **DutchBay_Figma_JSON.json** | JSON | Figma import tokens + 10-step setup instructions | Design team |
| **DutchBay_Prototype.html** | Interactive HTML | Clickable prototype with all 6 screens | Stakeholders, QA |
| **DutchBay_Design_System_v1.md** | Markdown | Living documentation reference | Designers, PMs |
| **README.md** (this file) | Markdown | Master index & implementation guide | Everyone |

---

## Quick Start

### For Front-End Developers

**Step 1: Import CSS**
```html
<!-- In your HTML head -->
<link rel="stylesheet" href="path/to/DutchBay_Design_System.css">
```

**Step 2: Use Design Tokens in HTML**
```html
<button class="btn btn-primary">Save Changes</button>
<div class="card">
  <h2 class="card-title">Revenue Trend</h2>
  <p class="typography-body-small-14 text-muted">20-year projection</p>
</div>
```

**Step 3: Use CSS Variables in Your Own Styles**
```css
/* Your component.css */
.my-component {
  color: var(--color-text-primary);
  background: var(--color-surface);
  padding: var(--spacing-md);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  transition: var(--transition-normal);
}

.my-component:hover {
  box-shadow: var(--shadow-lift);
}
```

**Step 4: Reference Interactive Prototype**
- Open `DutchBay_Prototype.html` in browser
- Toggle between portrait/landscape views
- See all 6 screens with working navigation tabs

---

### For Designers

**Step 1: Open Figma**
- Create new file: "Dutch Bay EPC – Design System v1.0"
- Start with shared library setup (see [Figma Setup](#figma-setup) below)

**Step 2: Import Design Tokens**
- Use `DutchBay_Figma_JSON.json`
- Follow 10-step installation guide embedded in JSON
- Alternative: Install Figma Tokens plugin for auto-import

**Step 3: Reference Documentation**
- Read `DutchBay_Design_System_v1.md` for all token definitions
- Review components section for interactive prototyping
- Use prototype HTML for user flow testing

---

## Color System

### Primary Colors

| Token | HEX | RGB | Usage |
|-------|-----|-----|-------|
| **Primary/Navy** | #1F2937 | 31, 41, 55 | Headers, primary text, top navigation |
| **Primary/Sky Blue** | #0A84FF | 10, 132, 255 | Links, buttons, active states, highlights |

**CSS Variables:**
```css
--color-primary-navy: #1F2937;
--color-primary-sky: #0A84FF;
```

### Neutral Colors (Gray Scale)

| Token | HEX | Usage |
|-------|-----|-------|
| **Gray 900** | #111827 | Primary body text (highest contrast) |
| **Gray 700** | #374151 | Secondary text, muted labels |
| **Gray 500** | #6B7280 | Placeholder text, disabled states |
| **Gray 300** | #D1D5DB | Borders, dividers |
| **Gray 200** | #E5E7EB | Secondary backgrounds, chart backgrounds |
| **Gray 100** | #F3F4F6 | Page background, light sections |
| **Gray 50** | #F9FAFB | Subtle backgrounds, hover states |
| **White** | #FFFFFF | Cards, surfaces, text background |

**CSS Variables:**
```css
--color-neutral-gray-900: #111827;
--color-neutral-gray-700: #374151;
/* ... and so on */
```

### Status Colors

| Token | HEX | Meaning | Use Case |
|-------|-----|---------|----------|
| **Success** | #10B981 | Green | Positive metrics, gains, good performance |
| **Warning** | #F59E0B | Amber | Caution, moderate alerts, needs attention |
| **Danger** | #EF4444 | Red | Errors, negative metrics, risk alerts |
| **Info** | #3B82F6 | Blue | Informational badges, notifications |

**With Light Variants:**
- Success Light: #D1FAE5 (background)
- Warning Light: #FEF3C7 (background)
- Danger Light: #FEE2E2 (background)
- Info Light: #DBEAFE (background)

**CSS Variables:**
```css
--color-status-success: #10B981;
--color-status-warning: #F59E0B;
--color-status-danger: #EF4444;
--color-status-info: #3B82F6;
```

### Chart Colors

Used specifically in financial visualizations:

| Token | HEX | Usage |
|-------|-----|-------|
| **Chart/Primary** | #0A84FF | Revenue, positive cash flows |
| **Chart/Secondary** | #EF4444 | Costs, negative flows, debt |
| **Chart/Tertiary** | #8B5CF6 | Forecasts, trends, projections |
| **Chart/Quaternary** | #06B6D4 | Capacity, utilization, secondary positive |

---

## Typography

### Type Scale

6 size categories with complete specifications:

| Category | Size | Weight | Line Height | Letter Spacing | Use |
|----------|------|--------|-------------|-----------------|-----|
| **Display/32** | 32px | 700 | 40px | -0.5px | Page titles, hero sections |
| **Header/28** | 28px | 700 | 36px | -0.5px | Major section headings |
| **Section Title/18** | 18px | 600 | 24px | -0.2px | Card titles, subsections |
| **Body/16** | 16px | 400 | 24px | 0px | Main body text, descriptions |
| **Body Small/14** | 14px | 400 | 20px | 0px | Secondary body, smaller text |
| **Caption/12** | 12px | 500 | 16px | 0.2px | Labels, captions, hints |
| **Metric Value/24** | 24px | 700 (mono) | 32px | -0.3px | Large financial numbers |
| **Metric Label/11** | 11px | 600 | 14px | 0.3px | Metric card labels |
| **Button/14** | 14px | 600 | 20px | 0px | Button text |
| **Tab Label/13** | 13px | 600 | 18px | 0px | Navigation tab labels |

### Font Families

- **Base:** `-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', Roboto, sans-serif`
  - Loads Inter from Google Fonts (recommended)
  - Falls back to system fonts for reliability

- **Monospace:** `'IBM Plex Mono', 'Monaco', 'Courier New', monospace`
  - Used for financial metrics and code blocks
  - Better readability for numbers

### CSS Usage

```css
/* Apply typography utilities */
<h1 class="typography-header-28">Dashboard</h1>
<p class="typography-body-16">Main content here</p>
<div class="typography-metric-value-24">$45.2M</div>
<label class="typography-metric-label-11">NPV</label>
```

Or use CSS variables directly:
```css
.custom-heading {
  font-size: var(--font-size-header-28);
  font-weight: var(--font-weight-header-28);
  line-height: var(--line-height-header-28);
}
```

---

## Components

### Buttons

**Primary Button (Default State)**
```html
<button class="btn btn-primary">Save Changes</button>
```

**Styles:**
- Background: #0A84FF
- Text: White
- Height: 48px
- Hover: #0066CC
- Active: #0052A3
- Disabled: Gray opacity 60%

**Sizes:**
```html
<button class="btn btn-sm btn-primary">Small</button>      <!-- 40px -->
<button class="btn btn-primary">Medium</button>            <!-- 48px (default) -->
<button class="btn btn-lg btn-primary">Large</button>      <!-- 56px -->
```

**Variants:**
```html
<button class="btn btn-primary">Primary Action</button>
<button class="btn btn-secondary">Secondary Action</button>
<button class="btn btn-full-width btn-primary">Full Width</button>
```

### Cards

**Basic Card**
```html
<div class="card">
  <h3 class="card-title">Revenue Trend</h3>
  <p class="card-subtitle">20-year projection</p>
  <div><!-- content --></div>
</div>
```

**With Header**
```html
<div class="card">
  <div class="card-header">
    <h3 class="card-title">Project Status</h3>
  </div>
  <div class="card-body">
    <!-- content -->
  </div>
</div>
```

**Metric Card (Colored Variants)**
```html
<!-- Positive trend (green) -->
<div class="card card-metric card-metric--positive">
  <p class="metric-label">NPV</p>
  <div class="metric-value">$45.2M</div>
</div>

<!-- Warning trend (amber) -->
<div class="card card-metric card-metric--warning">
  <!-- content -->
</div>

<!-- Negative trend (red) -->
<div class="card card-metric card-metric--negative">
  <!-- content -->
</div>
```

### Badges

```html
<span class="badge badge-success">Healthy</span>
<span class="badge badge-warning">Monitor</span>
<span class="badge badge-danger">At Risk</span>
<span class="badge badge-info">FYI</span>
```

### Form Elements

```html
<div class="form-group">
  <label class="form-label">Project Name</label>
  <input class="form-input" type="text" placeholder="Enter name">
</div>

<div class="form-group">
  <label class="form-label">Wind Resource (m/s)</label>
  <input class="form-input" type="number" value="8.5">
</div>

<div class="form-group">
  <label class="form-label">Description</label>
  <textarea class="form-textarea" placeholder="Type here..."></textarea>
</div>

<div class="form-group">
  <label class="form-label">Currency</label>
  <select class="form-select">
    <option>EUR</option>
    <option>USD</option>
    <option>GBP</option>
  </select>
</div>
```

### Navigation

**Top Navigation**
```html
<nav class="nav-top">
  <div class="nav-top-title">Dashboard</div>
  <button>⚙️</button>
</nav>
```

**Bottom Navigation (Tabs)**
```html
<nav class="nav-bottom">
  <a class="nav-bottom-item active" href="#dashboard">
    <div class="nav-bottom-icon">📊</div>
    <div class="nav-bottom-label">Dashboard</div>
  </a>
  <a class="nav-bottom-item" href="#scenarios">
    <div class="nav-bottom-icon">🎯</div>
    <div class="nav-bottom-label">Scenarios</div>
  </a>
  <a class="nav-bottom-item" href="#metrics">
    <div class="nav-bottom-icon">📈</div>
    <div class="nav-bottom-label">Metrics</div>
  </a>
  <a class="nav-bottom-item" href="#reports">
    <div class="nav-bottom-icon">📋</div>
    <div class="nav-bottom-label">Reports</div>
  </a>
  <a class="nav-bottom-item" href="#settings">
    <div class="nav-bottom-icon">⚙️</div>
    <div class="nav-bottom-label">Settings</div>
  </a>
</nav>
```

### Tables

```html
<table class="data-table">
  <thead>
    <tr>
      <th>Metric</th>
      <th>2026</th>
      <th>2027</th>
      <th>Status</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>DSCR</td>
      <td>1.32x</td>
      <td>1.45x</td>
      <td><span class="badge badge-success">✓</span></td>
    </tr>
  </tbody>
</table>
```

---

## Screens & Layouts

### 6 Portrait Screens (iPhone SE: 375×812px)

#### Screen 01: Dashboard
**Purpose:** Overview of project financials at a glance

**Sections:**
1. Top Navigation – "Dashboard" title + settings icon
2. Metric Cards (3-column grid):
   - NPV: $45.2M → "Healthy" badge
   - IRR: 12.8% → "On Track" badge
   - DSCR: 1.45x → "Safe" badge
3. Revenue Trend Card – 20-year projection chart
4. Project Status Table:
   - Capex → On Budget
   - Schedule → Monitor (warning)
   - Financing → Approved
5. Bottom Navigation (5 tabs): Dashboard (active), Scenarios, Metrics, Reports, Settings

#### Screen 02: Scenarios
**Purpose:** Compare multiple financial scenarios

**Sections:**
1. Scenario Cards (Base, Optimistic, Conservative):
   - Base Case: NPV $45.2M, IRR 12.8%, DSCR 1.45x → "Current"
   - Optimistic: NPV $67.8M, IRR 15.2%, DSCR 1.78x → "+50%"
   - Conservative: NPV $28.4M, IRR 9.3%, DSCR 1.21x → "-37%"
2. Sensitivity Analysis Card – Tornado chart placeholder

#### Screen 03: DSCR Detail
**Purpose:** Deep-dive into debt service coverage ratio

**Sections:**
1. Current DSCR Metric Card: 1.45x → "Healthy"
2. 20-Year Projection Chart
3. Year-by-Year Breakdown Table:
   - Shows 2026-2029 DSCR progression
   - All marked with ✓ checkmarks

#### Screen 04: Revenue & Costs
**Purpose:** Analyze revenue and cost projections

**Sections:**
1. Period Controls: 1Y (active), 5Y, 20Y
2. Metric Cards:
   - Revenue: $128.4M (positive)
   - Costs: $82.1M (negative)
   - EBITDA: $46.3M (positive)
3. Revenue vs Costs Chart
4. Cost Breakdown Table:
   - Turbine CAPEX: $58.2M
   - O&M: $35.9M
   - Grid Connection: $18.3M

#### Screen 05: Reports
**Purpose:** Access and download financial reports

**Sections:**
1. Financial Summary (Q4 2025) – View Report button
2. Annual Report (FY 2025) – Download PDF button
3. Sensitivity Analysis (Base Case) – Export button
4. Cash Flow Projection (20-year) – View Details button

#### Screen 06: Settings
**Purpose:** Configure project assumptions and preferences

**Sections:**
1. Project Settings Form:
   - Project Name: "Dutch Bay Wind Project"
2. Assumptions Form:
   - Wind Resource: 8.5 m/s
   - Tariff: €0.095/kWh
3. Notification Settings:
   - Email Alerts: Toggle ON
   - Daily Reports: Toggle OFF
4. Action Buttons:
   - Save Changes (primary)
   - Reset to Defaults (secondary)

### 3 Landscape Screens (iPhone SE: 812×375px)

**Landscape layouts available for:**
- Dashboard (metrics side-by-side with chart)
- Scenarios (3 scenario cards in row)
- Revenue & Costs (metrics column + chart)

---

## For Developers

### Implementation Checklist

- [ ] Import `DutchBay_Design_System.css` in main HTML
- [ ] Install Inter font from Google Fonts
- [ ] Create HTML structure matching screen layouts
- [ ] Apply class names from component reference
- [ ] Use CSS custom properties for custom styling
- [ ] Test responsive behavior (mobile, tablet, desktop)
- [ ] Test keyboard navigation and focus states
- [ ] Test dark mode toggle (if implementing)
- [ ] Validate HTML with W3C validator
- [ ] Test accessibility with axe DevTools

### CSS Custom Properties (Variables) Reference

**Most Common Variables:**

```css
/* Colors */
var(--color-primary-navy)
var(--color-primary-sky)
var(--color-text-primary)
var(--color-text-secondary)
var(--color-surface)
var(--color-background)
var(--color-status-success)
var(--color-status-warning)
var(--color-status-danger)

/* Typography */
var(--font-family-base)
var(--font-family-mono)
var(--font-size-header-28)
var(--font-weight-header-28)
var(--line-height-header-28)

/* Spacing */
var(--spacing-sm)     /* 8px */
var(--spacing-md)     /* 16px */
var(--spacing-lg)     /* 24px */

/* Effects */
var(--shadow-subtle)
var(--shadow-card)
var(--transition-normal)

/* Radius */
var(--radius-md)
var(--radius-lg)
```

### Example: Building a Custom Component

```css
.metric-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--spacing-md);
  box-shadow: var(--shadow-subtle);
  transition: var(--transition-normal);
}

.metric-card:hover {
  box-shadow: var(--shadow-card);
  cursor: pointer;
}

.metric-card__label {
  font-size: var(--font-size-metric-label-11);
  font-weight: var(--font-weight-metric-label-11);
  color: var(--color-text-muted);
  margin-bottom: var(--spacing-sm);
}

.metric-card__value {
  font-size: var(--font-size-metric-value-24);
  font-weight: var(--font-weight-metric-value-24);
  font-family: var(--font-family-mono);
  color: var(--color-text-primary);
}

.metric-card--positive .metric-card__value {
  color: var(--color-status-success);
}

.metric-card--negative .metric-card__value {
  color: var(--color-status-danger);
}
```

### Dark Mode Implementation

The CSS file includes dark mode support via media query:

```css
@media (prefers-color-scheme: dark) {
  :root {
    --color-background: #0F1419;
    --color-surface: #1A1F2E;
    --color-text-primary: #F9FAFB;
    --color-text-secondary: #D1D5DB;
    --color-text-muted: #9CA3AF;
    --color-border: #374151;
  }
}
```

Users with dark mode enabled in their OS settings will automatically get dark colors.

---

## For Designers

### Figma Workflow

**Prerequisites:**
- Figma account (free or paid)
- Inter font installed locally
- This README for reference

**Quick Setup:**
1. Create new Figma file: "Dutch Bay EPC – Design System"
2. Follow 10-step installation from `DutchBay_Figma_JSON.json`
3. Create component pages with variants
4. Link screens with prototype interactions
5. Share as shared library with team

### Component Setup in Figma

**Button/Primary Component:**
- Master component: 48px height, blue background
- Variants:
  - State: Default, Hover, Active, Disabled
  - Size: Small (40px), Medium (48px), Large (56px)
- Each variant is a separate layer with property controls

**Card Component:**
- Master component: white background, subtle shadow
- Variants:
  - Type: Standard, Metric, Data
  - Trend: Positive (green), Negative (red), Neutral (white)

See `DutchBay_Figma_JSON.json` for complete component specifications.

---

## Implementation Guide

### Frontend Project Setup

**Option 1: React/Next.js**
```bash
# Create directory structure
src/
├── styles/
│   ├── DutchBay_Design_System.css
│   └── index.css
├── components/
│   ├── Button.jsx
│   ├── Card.jsx
│   ├── Dashboard.jsx
│   └── ...
└── pages/
    └── Dashboard.jsx
```

```jsx
// In main.jsx or index.js
import './styles/DutchBay_Design_System.css'

// Use in components
<button className="btn btn-primary">Save</button>
<div className="card">...</div>
```

**Option 2: Vue.js**
```bash
src/
├── assets/
│   └── DutchBay_Design_System.css
├── components/
│   ├── Button.vue
│   ├── Card.vue
│   └── ...
└── App.vue
```

**Option 3: HTML/CSS/Vanilla JS**
```html
<!DOCTYPE html>
<html>
<head>
  <link rel="stylesheet" href="DutchBay_Design_System.css">
  <style>
    /* Your custom styles here */
  </style>
</head>
<body>
  <!-- Your HTML here -->
</body>
</html>
```

### Customization Example

To change the primary brand color throughout the app:

```css
/* In your app's main CSS file, after importing design system */
:root {
  --color-primary-sky: #FF6B35;  /* New brand color */
  --color-primary-navy: #004E89; /* New dark color */
}

/* All components using --color-primary-sky and --color-primary-navy
   automatically update */
```

---

## Figma Setup

### Complete 10-Step Installation

See embedded instructions in `DutchBay_Figma_JSON.json` for:

1. ✅ Prepare Figma file
2. ✅ Create color styles library (20 colors)
3. ✅ Create typography styles (10 text styles)
4. ✅ Create shadow styles (3 effects)
5. ✅ Create component pages
6. ✅ Build component variants
7. ✅ Create screen prototypes
8. ✅ Set up interactive prototype
9. ✅ Export for developers
10. ✅ Set up shared library for team

### Manual Import Alternative

If you prefer manual setup instead of using JSON:

1. **Colors Tab:** Add all 20 colors from color system section above
2. **Text Styles Tab:** Create text styles for each typography token
3. **Effects Tab:** Add 3 shadow styles
4. **Components:** Create master components for buttons, cards, inputs
5. **Screens:** Build 6 portrait + 3 landscape screens
6. **Prototype:** Link screens with navigation interactions

---

## Best Practices

### Color Usage

✅ **Do:**
- Use semantic color tokens (--color-primary-sky, --color-status-success)
- Maintain sufficient contrast (WCAG AA minimum 4.5:1)
- Use status colors for state indication only
- Pair colors with icons/text for colorblind accessibility

❌ **Don't:**
- Use hex codes directly in stylesheets (use CSS variables)
- Rely on color alone to convey information
- Mix color families (e.g., Navy + Teal)
- Use custom colors without design system approval

### Typography Usage

✅ **Do:**
- Use typography utilities for consistency
- Follow size hierarchy (larger = more important)
- Maintain adequate line-height for readability
- Use mono font for numbers/code

❌ **Don't:**
- Mix multiple font families
- Change font sizes without design approval
- Use all caps for body text
- Set very small font sizes (<12px) for body text

### Spacing Usage

✅ **Do:**
- Use spacing tokens (8px, 16px, 24px, 32px)
- Maintain consistent padding within components
- Group related items with spacing
- Use 8px grid for alignment

❌ **Don't:**
- Use arbitrary pixel values
- Mix spacing scales
- Add excessive whitespace
- Crowd related content

### Component Usage

✅ **Do:**
- Use provided components as-is when possible
- Extend components with additional classes
- Create new components by combining existing ones
- Document custom components

❌ **Don't:**
- Modify component core styles
- Ignore accessibility features
- Create duplicate components
- Bypass design system for quick fixes

---

## Troubleshooting

### Common Issues

**Q: Buttons look different in my browser**
- A: Ensure CSS file is imported BEFORE your custom styles
- Check browser support for CSS custom properties (modern browsers only)
- Clear browser cache (Ctrl+Shift+Delete)

**Q: Colors don't look right**
- A: Verify color token names match exactly (case-sensitive)
- Check parent element background color
- Use DevTools to inspect applied styles

**Q: Typography looks off**
- A: Install Inter font from Google Fonts
- Verify font-family includes system font fallbacks
- Check line-height values in parent container

**Q: Responsive layout breaks**
- A: Add CSS for mobile/tablet/desktop breakpoints
- Use media queries at 640px, 1024px breakpoints
- Test on actual devices, not just browser resize

**Q: Dark mode not working**
- A: Set `prefers-color-scheme: dark` in browser DevTools
- Or manually add `@media (prefers-color-scheme: dark)` override
- Ensure all colors have dark mode variants

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| **1.0.0** | 2025-12-07 | Initial release: 20 colors, 10 typography styles, 6 components, 6 screens |

---

## Support & Feedback

### Need Help?

1. **Design Questions** → Refer to Figma shared library
2. **Code Implementation** → Check CSS custom properties reference
3. **Component Usage** → See Components section above
4. **Accessibility Issues** → Test with axe DevTools, WCAG guidelines

### Suggest Changes

When proposing design system changes:
1. Document the change in detail
2. Update CSS, Figma, and documentation
3. Test across all screens and devices
4. Get approval from design team lead
5. Bump version number (e.g., 1.0.0 → 1.1.0)

---

## Credits & License

**Design System Created:** December 2025
**Project:** Dutch Bay Wind – Engineering, Procurement, Construction
**Location:** Sri Jayewardenepura Kotte, Western Province, Sri Lanka

---

**Last Updated:** 2025-12-07
**Maintainer:** Design System Team
**Status:** ✅ Production Ready
