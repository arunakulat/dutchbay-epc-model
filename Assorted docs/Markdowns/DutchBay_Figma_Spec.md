# Dutch Bay Wind Project – Figma Design System Specification
## Implementation Guide for Design & Engineering Handoff

**Figma File Structure | Component Definitions | Constraints & Variants**

---

## PART 1: FIGMA FILE STRUCTURE & ORGANIZATION

### Recommended Page Structure

```
DutchBay_EPC_v1.0 (Main File)
│
├── 📋 Cover (README page)
├── 🎨 Design Tokens (shared styles library)
├── 🧩 Components (reusable library)
├── 📱 Screens – iPhone SE (375px width)
│   ├── 01_Dashboard
│   ├── 02_Scenarios
│   ├── 03_DSCR_Detail
│   ├── 04_Revenue_Costs
│   ├── 05_Reports
│   ├── 06_Settings
│   └── Prototype (links all screens)
│
├── 📱 Screens – iPad (768px width) [Phase 2]
├── 💻 Screens – Desktop (1024px+) [Phase 2]
└── 🔧 Archive (deprecated components)
```

---

## PART 2: DESIGN TOKENS (FIGMA STYLES)

### How to Set Up in Figma

1. **Assets Panel** → Create **Style Library**
2. **Create Color Styles** with naming convention: `Color/[Category]/[Name]`
3. **Create Text Styles** with naming: `Typography/[Type]/[Size]`
4. **Export to shared library** for team access

### Color Styles (Figma Setup)

**Naming Convention:** `Color/[Semantic]/[Variant]`

```
Color/Primary/Navy
  Fill: #1F2937

Color/Primary/Sky Blue
  Fill: #0A84FF

Color/Neutral/Gray 900
  Fill: #111827

Color/Neutral/Gray 700
  Fill: #374151

Color/Neutral/Gray 500
  Fill: #6B7280

Color/Neutral/Gray 300
  Fill: #D1D5DB

Color/Neutral/Gray 200
  Fill: #E5E7EB

Color/Neutral/Gray 100
  Fill: #F3F4F6

Color/Neutral/Gray 50
  Fill: #F9FAFB

Color/Status/Success
  Fill: #10B981

Color/Status/Success Light
  Fill: #D1FAE5

Color/Status/Warning
  Fill: #F59E0B

Color/Status/Warning Light
  Fill: #FEF3C7

Color/Status/Danger
  Fill: #EF4444

Color/Status/Danger Light
  Fill: #FEE2E2

Color/Status/Info
  Fill: #3B82F6

Color/Status/Info Light
  Fill: #DBEAFE

Color/Chart/Primary
  Fill: #0A84FF

Color/Chart/Secondary
  Fill: #EF4444

Color/Chart/Tertiary
  Fill: #8B5CF6

Color/Chart/Quaternary
  Fill: #06B6D4
```

### Typography Styles (Figma Setup)

**Naming Convention:** `Typography/[Category]/[Size]`

```
Typography/Display/32
  Font: Inter
  Weight: 700
  Size: 32px
  Line Height: 40px
  Letter Spacing: -0.5px

Typography/Header/28
  Font: Inter
  Weight: 700
  Size: 28px
  Line Height: 36px
  Letter Spacing: -0.5px

Typography/Section Title/18
  Font: Inter
  Weight: 600
  Size: 18px
  Line Height: 24px
  Letter Spacing: -0.2px

Typography/Body/16
  Font: Inter
  Weight: 400
  Size: 16px
  Line Height: 24px
  Letter Spacing: 0px

Typography/Body Small/14
  Font: Inter
  Weight: 400
  Size: 14px
  Line Height: 20px
  Letter Spacing: 0px

Typography/Caption/12
  Font: Inter
  Weight: 500
  Size: 12px
  Line Height: 16px
  Letter Spacing: 0.2px

Typography/Metric Value/24
  Font: IBM Plex Mono (or Inter)
  Weight: 700
  Size: 24px
  Line Height: 32px
  Letter Spacing: -0.3px

Typography/Metric Label/11
  Font: Inter
  Weight: 600
  Size: 11px
  Line Height: 14px
  Letter Spacing: 0.3px

Typography/Button/14
  Font: Inter
  Weight: 600
  Size: 14px
  Line Height: 20px
  Letter Spacing: 0px

Typography/Tab Label/13
  Font: Inter
  Weight: 600
  Size: 13px
  Line Height: 18px
  Letter Spacing: 0px
```

### Shadow Styles

```
Shadow/Subtle
  X: 0, Y: 1, Blur: 3, Spread: 0
  Color: #000000, Opacity: 10%

Shadow/Card
  X: 0, Y: 4, Blur: 12, Spread: 0
  Color: #000000, Opacity: 15%

Shadow/Lift
  X: 0, Y: 10, Blur: 25, Spread: 0
  Color: #000000, Opacity: 20%
```

---

## PART 3: COMPONENT LIBRARY (REUSABLE COMPONENTS)

### Component Naming & Variants

**Figma Structure:** `Components > [Category] > [Component Name]`

### Buttons (Component Group)

#### Primary Button

```
Component: Button/Primary
Variants:
  - State: Default | Hover | Active | Disabled | Loading
  - Size: Small (40px) | Medium (48px) | Large (56px)

Default State:
  Background: Color/Primary/Sky Blue (#0A84FF)
  Text: Typography/Button/14 + Color/Neutral/White
  Padding: 12px vertical × 20px horizontal
  Corner Radius: 8px
  Height: 48px
  Icon (optional): 20px, left side, 8px margin-right

Hover State:
  Background: #0066CC (darken by 20%)
  Cursor: pointer
  Transform: none (handled in code)

Active State:
  Background: #0052A3 (darken by 40%)
  Opacity: 0.95

Disabled State:
  Background: Color/Neutral/Gray 300
  Text: Color/Neutral/Gray 400
  Opacity: 0.6
  Cursor: not-allowed

Loading State:
  Background: Color/Primary/Sky Blue
  Text: "Loading..."
  Icon: Spinner (16px, white, animated in code)
  Disabled: true
```

#### Secondary Button

```
Component: Button/Secondary
Variants:
  - State: Default | Hover | Active | Disabled
  - Size: Small | Medium | Large

Default State:
  Background: Color/Neutral/Gray 100 (#F3F4F6)
  Border: 1px, Color/Neutral/Gray 300
  Text: Typography/Button/14 + Color/Primary/Navy
  Padding: 12px × 20px
  Corner Radius: 8px
  Height: 48px

Hover State:
  Background: Color/Neutral/Gray 200
  Border: 1px, Color/Neutral/Gray 400

Active State:
  Background: Color/Neutral/Gray 300
  Border: 1px, Color/Neutral/Gray 500

Disabled State:
  Background: Color/Neutral/Gray 50
  Border: 1px, Color/Neutral/Gray 300
  Text: Color/Neutral/Gray 400
  Opacity: 0.5
```

#### Icon Button

```
Component: Button/Icon
Variants:
  - State: Default | Hover | Active | Disabled
  - Icon: Settings | Close | Menu | Back | More | [others]

Default State:
  Background: transparent
  Icon: 24px, Color/Primary/Navy
  Padding: 12px (48×48px touch target)
  Corner Radius: 8px

Hover State:
  Background: Color/Neutral/Gray 100
  Icon: Color/Primary/Sky Blue

Active State:
  Background: Color/Neutral/Gray 200
  Icon: Color/Primary/Sky Blue

Disabled State:
  Icon: Color/Neutral/Gray 400
  Opacity: 0.5
```

### Input Fields (Component Group)

#### Text Input

```
Component: Input/Text
Variants:
  - State: Default | Focused | Error | Disabled | Success
  - Size: Standard (48px) | Compact (40px)
  - Icon: None | Left | Right

Default State:
  Background: Color/Neutral/White
  Border: 1px, Color/Neutral/Gray 300
  Corner Radius: 8px
  Height: 48px
  Padding: 12px 14px
  Text: Typography/Body Small/14
  Placeholder: Typography/Body Small/14, Color/Neutral/Gray 400
  Icon (optional): 20px, left 14px, Color/Neutral/Gray 500

Focused State:
  Border: 2px, Color/Primary/Sky Blue
  Box Shadow: 0 0 0 3px rgba(10, 132, 255, 0.1)
  Outline: none

Error State:
  Border: 2px, Color/Status/Danger
  Box Shadow: 0 0 0 3px rgba(239, 68, 68, 0.1)
  Icon: Alert (20px, right, Color/Status/Danger)

Success State:
  Border: 2px, Color/Status/Success
  Icon: Checkmark (20px, right, Color/Status/Success)

Disabled State:
  Background: Color/Neutral/Gray 100
  Border: 1px, Color/Neutral/Gray 300
  Text: Color/Neutral/Gray 400
  Cursor: not-allowed
  Opacity: 0.6
```

#### Form Label & Error Text

```
Component: Form/Label
  Text: Typography/Body Small/14, Weight 600
  Margin Bottom: 8px
  Required Indicator (*): Color/Status/Danger (optional)

Component: Form/Error
  Text: Typography/Caption/12, Weight 500, Color/Status/Danger
  Icon: Alert triangle (12px, #EF4444)
  Margin Top: 4px
```

### Cards (Component Group)

#### Standard Card

```
Component: Card/Standard
Variants:
  - State: Default | Hover | Active
  - Padding: Standard (16px) | Compact (12px)

Default State:
  Background: Color/Neutral/White
  Border: 1px, Color/Neutral/Gray 200
  Corner Radius: 12px
  Padding: 16px
  Shadow: Shadow/Subtle
  Margin Bottom: 16px

Hover State (if interactive):
  Shadow: Shadow/Card
  Transform: translateY(-2px) [in code, not in Figma]
  Border: 1px, Color/Neutral/Gray 300

Active/Selected State:
  Border: 2px, Color/Primary/Sky Blue
  Shadow: Shadow/Lift
```

#### Metric Card

```
Component: Card/Metric
Variants:
  - Trend: Positive | Negative | Neutral
  - Size: Standard | Compact

Layout (Vertical Stack):
  - Label (top): Typography/Metric Label/11, Color/Neutral/Gray 600
  - Value (center): Typography/Metric Value/24, color varies:
      Positive: Color/Status/Success
      Negative: Color/Status/Danger
      Neutral: Color/Primary/Navy
  - Status Badge (optional): 8px top margin

Background Options:
  Positive: #F0FDFB (very light green)
  Negative: #FEF2F2 (very light red)
  Neutral: #FFFFFF (standard white)

Padding: 16px
Corner Radius: 12px
Border: 1px, Color/Neutral/Gray 200 (or variant of bg color)
```

#### Data Card (Table/List Container)

```
Component: Card/Data
Variants:
  - Density: Standard (56px) | Compact (48px)

Card Container:
  Background: Color/Neutral/White
  Border: 1px, Color/Neutral/Gray 200
  Corner Radius: 12px
  Padding: 0px (table fills card)

Header Row (inside card):
  Background: Color/Neutral/Gray 50
  Padding: 12px 16px
  Border Bottom: 1px, Color/Neutral/Gray 200
  Text: Typography/Table Header/12, Color/Neutral/Gray 600

Data Row:
  Padding: 12px 16px
  Height: 56px (standard) or 48px (compact)
  Border Bottom: 1px, Color/Neutral/Gray 100 (last row: none)
  Text: Typography/Table Cell/14, Color/Primary/Navy
  Hover: Background Color/Neutral/Gray 50 [optional]
```

### Status Indicators & Badges

#### Status Badge

```
Component: Badge/Status
Variants:
  - Status: Success | Warning | Danger | Info

Success Badge:
  Background: Color/Status/Success Light (#D1FAE5)
  Text: Typography/Caption/12, Color/Status/Success Dark (#047857)
  Border: 1px, #A7F3D0
  Padding: 4px 8px
  Corner Radius: 20px (full pill)
  Icon (optional): Checkmark (12px, #047857)

Warning Badge:
  Background: Color/Status/Warning Light (#FEF3C7)
  Text: Color/Status/Warning Dark (#B45309)
  Border: 1px, #FECB45
  Padding: 4px 8px
  Corner Radius: 20px

Danger Badge:
  Background: Color/Status/Danger Light (#FEE2E2)
  Text: Color/Status/Danger Dark (#991B1B)
  Border: 1px, #FCBDBD
  Padding: 4px 8px
  Corner Radius: 20px

Info Badge:
  Background: Color/Status/Info Light (#DBEAFE)
  Text: Color/Status/Info Dark (#1E40AF)
  Border: 1px, #93C5FD
  Padding: 4px 8px
  Corner Radius: 20px
```

#### Inline Status Indicator (dot + text)

```
Component: Indicator/Status
Variants:
  - Status: Success | Warning | Danger | Info

Layout (Horizontal):
  - Dot: 8px diameter, Color/Status/[Status]
  - Text: Typography/Body Small/14, Color matches dot
  - Spacing: 8px between dot and text
```

### Charts & Visualizations

#### Line Chart Container

```
Component: Chart/Line
Variants:
  - Series Count: Single | Dual | Multi
  - Height: Standard (240px) | Tall (320px)

Container:
  Background: Color/Neutral/Gray 100 (#F3F4F6)
  Border: 1px, Color/Neutral/Gray 200
  Corner Radius: 12px
  Padding: 16px
  Min Height: 240px

Chart Area:
  Background: Color/Neutral/Gray 100
  Grid Lines: 1px, Color/Neutral/Gray 200, light opacity

Title (inside card):
  Text: Typography/Body/16, Weight 600, Color/Primary/Navy
  Margin Bottom: 8px

Subtitle (inside card):
  Text: Typography/Body Small/14, Color/Neutral/Gray 500
  Margin Bottom: 12px

Legend (top-right):
  Chips with color dots
  Text: Typography/Caption/12
  Spacing: 8px between chips

Line (data):
  Width: 2px
  Color: per series (Sky Blue, Red, Purple, Cyan)
  Stroke: Smooth (bezier curve)

Data Point (optional):
  Size: 4px diameter
  Color: line color
  Hover: 6px + shadow

Axes:
  Text: Typography/Caption/12, Color/Neutral/Gray 600
  Lines: 1px, Color/Neutral/Gray 300
```

#### Bar Chart Container

```
Component: Chart/Bar
Variants:
  - Type: Single | Stacked
  - Orientation: Vertical | Horizontal

Same structure as Line Chart, but:

Bar (data):
  Width: calculated per count (max 40px, min 8px)
  Color: per category or series
  Corner Radius: 4px top corners only
  Spacing: 4px between bars

Stacked Bar (cost breakdown):
  Segments: Multiple colors stacked vertically
  Colors: per category (Turbine CAPEX, O&M, etc.)
  Label: on hover or external legend
```

### Navigation Components

#### Bottom Navigation Bar (iOS Tab Bar style)

```
Component: Navigation/Bottom
Variants:
  - Tab Active: Dashboard | Scenarios | Metrics | Reports | Settings

Container:
  Position: Fixed bottom
  Height: 80px (includes 20px safe area)
  Background: Color/Neutral/White
  Border Top: 1px, Color/Neutral/Gray 200
  Display: Flex, space-around

Per Tab (child component):
  Width: 20% (5 tabs)
  Height: 60px (80px minus safe area)
  Flex direction: Column, align-center
  Padding: 8px 0

Inactive Tab:
  Icon: 24px, Color/Neutral/Gray 500
  Label: Typography/Tab Label/13, Color/Neutral/Gray 500
  Spacing: 4px between icon and label

Active Tab:
  Icon: 24px, Color/Primary/Sky Blue
  Label: Typography/Tab Label/13, Color/Primary/Sky Blue
  Indicator (optional): 2px line above, Color/Primary/Sky Blue
```

#### Top Navigation Bar (Header)

```
Component: Navigation/Top
Variants:
  - Layout: Default | with Subtitle | with Actions

Container:
  Height: 56px
  Background: Color/Primary/Navy (#1F2937)
  Padding: 0 16px
  Safe Area Top: +20px or +44px (if notched)

Left Section:
  Back Button: Icon Button (24px, white)
  OR Logo: 24px, white

Center Section:
  Title: Typography/Header/28, Color/Neutral/White
  Alignment: Center or left-aligned
  Subtitle (optional): Typography/Body Small/14, Color/Neutral/Gray 200

Right Section:
  Action Buttons: Icon Buttons, 24px, white
  Spacing: 16px between buttons
  Max width: 96px (2–3 buttons)
```

### Form Components

#### Checkbox

```
Component: Form/Checkbox
Variants:
  - State: Unchecked | Checked | Disabled

Container:
  Size: 20×20px
  Border: 2px, Color/Neutral/Gray 300
  Corner Radius: 4px
  Background (unchecked): Color/Neutral/White

Checked State:
  Background: Color/Primary/Sky Blue
  Border: 2px, Color/Primary/Sky Blue
  Icon: Checkmark (12px, white, 2px stroke)
  Animation: Bounce in (100ms)

Disabled State:
  Background: Color/Neutral/Gray 100
  Border: 2px, Color/Neutral/Gray 300
  Opacity: 0.6

Label (adjacent):
  Text: Typography/Body Small/14
  Margin Left: 8px
  Touch target: Extends to label
```

#### Radio Button

```
Component: Form/Radio
Variants:
  - State: Unchecked | Checked | Disabled

Container:
  Size: 20×20px
  Border: 2px, Color/Neutral/Gray 300
  Corner Radius: 50% (circle)
  Background: Color/Neutral/White

Checked State:
  Border: 2px, Color/Primary/Sky Blue
  Inner dot: 8px diameter, Color/Primary/Sky Blue
  Animation: Dot appears (100ms)

Disabled State:
  Border: 2px, Color/Neutral/Gray 300
  Background: Color/Neutral/Gray 100
  Opacity: 0.6

Label: Same as checkbox
```

#### Toggle Switch

```
Component: Form/Toggle
Variants:
  - State: Off | On | Disabled

Container:
  Width: 48px
  Height: 28px
  Corner Radius: 14px
  Background (off): Color/Neutral/Gray 300
  Padding: 2px

Knob:
  Size: 24×24px (minus padding)
  Background: Color/Neutral/White
  Corner Radius: 12px
  Position: left (off) or right (on)
  Animation: Slide (200ms ease-out)

On State:
  Background: Color/Primary/Sky Blue
  Knob: positioned right

Disabled State:
  Background: Color/Neutral/Gray 200
  Opacity: 0.5
  Cursor: not-allowed
```

#### Select Dropdown

```
Component: Form/Select
Variants:
  - State: Default | Focused | Open | Disabled

Trigger Button:
  Height: 48px
  Background: Color/Neutral/White
  Border: 1px, Color/Neutral/Gray 300
  Corner Radius: 8px
  Padding: 12px 14px
  Text: Typography/Body Small/14
  Icon (right): Chevron down (16px), Color/Neutral/Gray 500

Focused State:
  Border: 2px, Color/Primary/Sky Blue
  Box Shadow: 0 0 0 3px rgba(10, 132, 255, 0.1)

Open State:
  Border: 2px, Color/Primary/Sky Blue
  Icon (right): Chevron up

Dropdown Menu:
  Position: Below trigger (auto-flip if bottom edge near)
  Background: Color/Neutral/White
  Border: 1px, Color/Neutral/Gray 200
  Corner Radius: 8px
  Box Shadow: Shadow/Lift
  Z-index: 1000
  Max Height: 200px (scrollable)

Menu Item (child):
  Padding: 12px 14px
  Text: Typography/Body Small/14
  Min Height: 40px
  Background (default): Color/Neutral/White
  Background (hover): Color/Neutral/Gray 100
  Background (selected): Color/Primary/Sky Blue + 10% opacity
  Text (selected): Color/Primary/Sky Blue
```

---

## PART 4: SCREEN TEMPLATES & CONSTRAINTS

### iPhone SE Screen (375px width)

#### Master Frame

```
Frame Name: "iPhone SE Master"
Width: 375px
Height: 812px (full height with safe areas)
Background: Color/Neutral/Gray 50

Safe Area Insets:
  Top: 44px (status bar + notch if applicable; SE has none)
  Bottom: 34px (home indicator) or 20px on older SE
  Left: 0px
  Right: 0px

Grid: 8px (for snapping)
```

#### Content Area

```
Scrollable Content Container:
  Width: 343px (375px - 16px padding both sides)
  Top Padding: 16px (below top nav or status bar)
  Bottom Padding: 24px (above bottom nav, which is 80px)
  Horizontal Padding: 16px (left & right)
  Column Gap: 16px (between vertical stacks)
```

### Responsive Breakpoints (Phase 2+)

```
iPad (768px):
  Frame: 768×1024px (portrait)
  Content: Max width 728px (768px - 40px padding)
  Grid: 8px
  Columns: 2-up layout for cards

Landscape iPad (1024px):
  Frame: 1024×768px
  Content: Max width 960px
  Columns: 3–4 columns for data tables

Desktop (1280px+):
  Frame: 1280px wide
  Content: Max width 1200px (centered)
  Columns: 4–6 columns
  Sidebar: 240px left sidebar (navigation)
```

---

## PART 5: PROTOTYPING & INTERACTIONS

### Interaction Setup in Figma

#### Screen Navigation

```
Frame: Dashboard
  [Tap] "Scenarios" tab → Frame: Scenarios
  [Tap] "Metrics" tab → Frame: DSCR_Detail
  [Tap] "Reports" tab → Frame: Reports
  [Tap] "Settings" tab → Frame: Settings

Transition: Push right (200ms ease-out)
Maintain scroll position: true
```

#### Modal Interactions

```
Frame: Dashboard
  [Tap] "View Details" button → Modal: Metric_Details
  Transition: Overlay fade-in (150ms)
  Dismiss on: Tap outside OR tap "Close" button
  Transition out: Fade-out (150ms)
```

#### Form Validation

```
Frame: Settings > Input Field
  [Focus] → Show hint text (always visible)
  [Type] → Validate on blur (500ms delay)
  [Invalid] → Border turns red, error text appears
  [Fix & Blur] → Error clears, green checkmark appears
```

### Micro-interaction Examples

#### Button Press Feedback

```
Button: Primary
  [On press] → Overlay opacity 0 → 0.1 (50ms)
  [On release] → Overlay opacity 0.1 → 0 (150ms ease-out)

In code:
    button:active { transform: scale(0.98); }
```

#### Loading State

```
Component: Card with data
  [Initial] → Skeleton placeholder (pulse animation)
  [Loading] → Spinner appears (24px, centered)
  [Complete] → Fade out skeleton, fade in real content (200ms)
```

---

## PART 6: HANDOFF CHECKLIST FOR DEVELOPERS

### Design Documentation Checklist

- [ ] All colors defined as Figma color styles (shared library)
- [ ] All typography defined as Figma text styles
- [ ] All components have proper naming convention
- [ ] All components have visible variants (state machine)
- [ ] All buttons have 48px minimum height (touch target)
- [ ] All form inputs have 48px height
- [ ] Dark mode variants created for all colors (Phase 2)
- [ ] Accessibility specs documented (contrast ratios, focus states)
- [ ] Micro-interactions documented (in notes/prototyping)
- [ ] Safe area constraints applied to frames
- [ ] Icon library organized and named
- [ ] Animation timings documented (in component notes)
- [ ] Responsive layout rules specified (breakpoints)
- [ ] All screens have proper naming hierarchy

### Developer Handoff Deliverables

1. **Figma File:** Shared with "View" access to engineers
2. **Design System Document:** This markdown file + full specs
3. **Component Stories:** Figma links to each component + variants
4. **Prototype:** Interactive prototype with navigation links
5. **Spacing Grid Reference:** 8px grid visual guide
6. **Color & Typography Reference:** Exported as CSS custom properties

### Export Specifications (for CSS/Code)

**Export Format:**

```css
/* Colors (CSS Custom Properties) */
:root {
  --color-primary-navy: #1F2937;
  --color-primary-sky: #0A84FF;
  --color-neutral-gray-900: #111827;
  --color-status-success: #10B981;
  /* ... etc */
}

/* Typography (CSS Classes) */
.typography-header-28 {
  font-family: 'Inter', sans-serif;
  font-size: 28px;
  font-weight: 700;
  line-height: 36px;
  letter-spacing: -0.5px;
}

.typography-body-16 {
  font-family: 'Inter', sans-serif;
  font-size: 16px;
  font-weight: 400;
  line-height: 24px;
  letter-spacing: 0px;
}
```

---

## PART 7: QUALITY ASSURANCE CHECKLIST

### Before Design Handoff

- [ ] All frames labeled and organized
- [ ] No "Copy of" or untitled components
- [ ] All text uses defined text styles (no manual text)
- [ ] All fills use defined color styles (no hex #ABCDEF typed)
- [ ] All shadows use defined shadow styles
- [ ] Component constraints set correctly (responsive behavior)
- [ ] No rasterized/flattened elements (keep vectors)
- [ ] All icons organized in icon library
- [ ] Components have descriptions (in Figma notes)
- [ ] Prototype is tested and working
- [ ] All variants documented with clear labels
- [ ] Font files embedded or specified

### Accessibility QA

- [ ] Color contrast checked (Figma plugin: Contrast)
- [ ] Focus indicators visible on all interactive elements
- [ ] Touch targets minimum 48px
- [ ] Form labels associated with inputs
- [ ] Icon-only buttons have aria-label or tooltip
- [ ] Error messages clear and specific
- [ ] Animation respects prefers-reduced-motion

---

## APPENDIX: FIGMA SHORTCUTS & PLUGINS

### Recommended Figma Plugins

1. **Stark** – Accessibility checker (contrast, color blindness)
2. **Color Contrast Checker** – WCAG compliance
3. **System UI Kit Exporter** – Export tokens to CSS
4. **Figma to Code** – Basic HTML/CSS export (starting point)
5. **Measure** – Inspect distances, spacing

### Figma Shortcuts (Mac)

```
Cmd + Option + C  → Copy style/component
Cmd + Option + V  → Paste style/component
Cmd + D           → Duplicate element
Cmd + R           → Rename
Shift + 2         → Text tool
F                 → Frame tool
G                 → Group (Shift + G to ungroup)
```

---

## Version Control & Change Log

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| **v1.0** | Dec 2025 | Initial component library & design system | Design Team |
| **v1.1** | TBD | Dark mode variants | Design Team |
| **v1.2** | TBD | iPad/landscape layouts | Design Team |
| **v2.0** | TBD | Web (1024px+) design system | Design Team |

---

## Contact & Support

- **Design Lead:** [Name]
- **Questions:** Post in #design-system Slack channel
- **Component Requests:** Submit via [GitHub Issues or Jira]
- **Updates:** Check Figma file version history

**Figma File Link:** [Share link]
**Last Updated:** December 2025
