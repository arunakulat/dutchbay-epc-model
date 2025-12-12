# Dutch Bay Wind Project – Complete Design System v1.0

**Status:** Living Document | **Last Updated:** December 2025 | **Audience:** Design & Engineering Teams

---

## Table of Contents

1. [Foundation](#foundation)
2. [Typography System](#typography-system)
3. [Color System](#color-system)
4. [Spacing & Layout](#spacing--layout)
5. [Component Library](#component-library)
6. [Interactive States](#interactive-states)
7. [Dark Mode](#dark-mode)
8. [Accessibility](#accessibility)
9. [Micro-interactions](#micro-interactions)
10. [iOS/Android Adaptations](#iosandroid-adaptations)

---

## Foundation

### Core Principles

- **Clarity First:** Financial data must be immediately understandable
- **Trust Through Consistency:** Predictable patterns build confidence
- **Accessibility Inherent:** WCAG AA compliance non-negotiable
- **Cross-Platform Native:** Respect iOS/Android affordances
- **Data-Driven Design:** Visual hierarchy serves information hierarchy

### Target Devices (MVP Phase)

- **iOS:** iPhone SE (375px width) → iPad (768px+)
- **Android:** Pixel 6 (412px) → Tablets (768px+)
- **Web:** 1024px+ (Phase 2)

---

## Typography System

### Font Stack (Unified Cross-Platform)

```
Primary Font: Inter (Google Fonts, free)
  • Licensed: Open Font License
  • Support: iOS, Android, Web
  • Fallback: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto

Monospace Font: IBM Plex Mono (for financial tables/code)
  • Usage: Large numbers, currency values, ticker symbols
  • Sizes: 11px–24px
```

### Type Scale – Complete Definition

| Element | Size | Weight | Line Height | Letter Spacing | Usage | Min Contrast |
|---------|------|--------|-------------|----------------|-------|--------------|
| **Display/Hero** | 32px | 700 | 40px | -0.5px | App title screens | 7:1 |
| **Header/Title** | 28px | 700 | 36px | -0.5px | Screen titles, modals | 7:1 |
| **Section Title** | 18px | 600 | 24px | -0.2px | Card headers, section breaks | 7:1 |
| **Subtitle** | 16px | 500 | 24px | 0px | Secondary headings, descriptions | 7:1 |
| **Body Copy** | 16px | 400 | 24px | 0px | Primary content, descriptions | 4.5:1 |
| **Body Small** | 14px | 400 | 20px | 0px | Secondary text, hints, labels | 4.5:1 |
| **Caption** | 12px | 500 | 16px | 0.2px | Metadata, timestamps, hints | 4.5:1 |
| **Metric Value** | 24px | 700 | 32px | -0.3px | Large numbers (NPV, IRR, %) | 7:1 |
| **Metric Label** | 11px | 600 | 14px | 0.3px | Above/below metric values | 4.5:1 |
| **Tab Label** | 13px | 600 | 18px | 0px | Bottom/top navigation tabs | 4.5:1 |
| **Button Label** | 14px | 600 | 20px | 0px | Button text (all buttons) | 4.5:1 |
| **Input Placeholder** | 14px | 400 | 20px | 0px | Form placeholders | 3:1 (relaxed) |
| **Table Header** | 12px | 600 | 16px | 0px | Column headers in tables | 7:1 |
| **Table Cell** | 14px | 400 | 20px | 0px | Table data cells | 4.5:1 |
| **Badge/Chip Label** | 11px | 500 | 14px | 0.1px | Badge/chip text | 4.5:1 |
| **Tooltip Text** | 12px | 400 | 16px | 0px | Tooltip content | 4.5:1 |

### Line Height Ratios (Responsive)

- **Tight (1.2x):** Headers, display text
- **Normal (1.5x):** Body copy, high readability
- **Relaxed (1.6x):** Forms, accessibility-critical content

### Weight Scale (Inter Font)

- **400:** Regular (body text, most content)
- **500:** Medium (secondary emphasis, labels, captions)
- **600:** Semibold (headers, buttons, metric labels)
- **700:** Bold (display, metric values, emphasis)

---

## Color System

### Primary Brand Colors

| Name | HEX | RGB | Usage | Accessibility |
|------|-----|-----|-------|----------------|
| **Navy Blue (Primary Dark)** | #1F2937 | 31, 41, 55 | Headers, primary text, emphasis | Text on white: 8.2:1 ✓ |
| **Sky Blue (Primary Light/Accent)** | #0A84FF | 10, 132, 255 | Links, active states, CTAs, highlights | Text on white: 4.8:1 ✓ |
| **White (Surface)** | #FFFFFF | 255, 255, 255 | Card backgrounds, containers | — |

### Neutral Palette (Grays)

| Name | HEX | RGB | Usage | Notes |
|------|-----|-----|-------|-------|
| **Gray 900** | #111827 | 17, 24, 39 | Primary body text | Highest contrast |
| **Gray 800** | #1F2937 | 31, 41, 55 | Secondary headers | Same as Navy |
| **Gray 700** | #374151 | 55, 65, 81 | Secondary text, muted labels | Standard text gray |
| **Gray 600** | #4B5563 | 75, 85, 99 | Tertiary text, disabled states | Slightly lighter |
| **Gray 500** | #6B7280 | 107, 114, 128 | Placeholder, disabled, hints | Light gray |
| **Gray 400** | #9CA3AF | 156, 163, 175 | Light borders, subtle dividers | Very light |
| **Gray 300** | #D1D5DB | 209, 213, 219 | Borders, dividers, rules | Standard border |
| **Gray 200** | #E5E7EB | 229, 231, 235 | Secondary backgrounds, chart BG | Light section |
| **Gray 100** | #F3F4F6 | 243, 244, 246 | Page background, light sections | Very light background |
| **Gray 50** | #F9FAFB | 249, 250, 251 | Subtle backgrounds, hover states | Lightest |

### Semantic Colors – Status & Performance

#### Success (Green)

| Name | HEX | RGB | Usage |
|------|-----|-----|-------|
| **Success** | #10B981 | 16, 185, 129 | Positive metrics, gains, good performance |
| **Success Light** | #D1FAE5 | 209, 250, 229 | Success card backgrounds, badges |
| **Success Dark** | #047857 | 4, 120, 87 | Success text on light backgrounds |

#### Warning (Orange)

| Name | HEX | RGB | Usage |
|------|-----|-----|-------|
| **Warning** | #F59E0B | 245, 158, 11 | Warnings, moderate caution, alerts |
| **Warning Light** | #FEF3C7 | 254, 243, 199 | Warning card backgrounds |
| **Warning Dark** | #B45309 | 180, 83, 9 | Warning text on light backgrounds |

#### Danger (Red)

| Name | HEX | RGB | Usage |
|------|-----|-----|-------|
| **Danger** | #EF4444 | 239, 68, 68 | Errors, negative metrics, debt, risks |
| **Danger Light** | #FEE2E2 | 254, 226, 226 | Error card backgrounds, badges |
| **Danger Dark** | #991B1B | 153, 27, 27 | Danger text on light backgrounds |

#### Information (Blue)

| Name | HEX | RGB | Usage |
|------|-----|-----|-------|
| **Info** | #3B82F6 | 59, 130, 246 | Info badges, notifications, secondary CTA |
| **Info Light** | #DBEAFE | 219, 234, 254 | Info card backgrounds |
| **Info Dark** | #1E40AF | 30, 64, 175 | Info text on light backgrounds |

### Chart & Data Visualization Colors

| Name | HEX | RGB | Purpose |
|------|-----|-----|---------|
| **Chart Primary** | #0A84FF | 10, 132, 255 | Revenue, positive flows, primary metric |
| **Chart Secondary** | #EF4444 | 239, 68, 68 | Costs, negative flows, debt |
| **Chart Tertiary** | #8B5CF6 | 139, 92, 246 | Forecast, trend, projection |
| **Chart Quaternary** | #06B6D4 | 6, 182, 212 | Capacity, utilization, secondary positive |
| **Chart Quinary** | #10B981 | 16, 185, 129 | Growth, cumulative positive |
| **Chart Background** | #F3F4F6 | 243, 244, 246 | Chart container background |
| **Chart Neutral** | #6B7280 | 107, 114, 128 | Axis labels, grid lines, neutral data |

### Performance Gradient (Low → High)

```
Low Performance:   #EF4444 (Red) at -$50M
Mid Performance:   #F59E0B (Orange) at $0
High Performance:  #10B981 (Green) at $100M+

Used for: Sensitivity analysis, tornado charts, heatmaps
Interpolate smoothly between values
```

### Tonal Variants (Material Design 3 Support)

For Android Material 3 buttons, cards, and badges:

| Base Color | Tonal Light | Usage |
|-----------|------------|-------|
| Navy (#1F2937) | #E8EEF7 | Tonal buttons, secondary cards |
| Sky Blue (#0A84FF) | #E0F1FF | Tonal accent buttons |
| Success (#10B981) | #E6F9F1 | Tonal success buttons |
| Warning (#F59E0B) | #FEF5E6 | Tonal warning buttons |
| Danger (#EF4444) | #FCE8E8 | Tonal danger buttons |

---

## Spacing & Layout

### 8px Grid System (Core)

```
Base Unit: 8px
All spacing MUST use multiples of 8px
Exception: 4px for micro-spacing (text leading, icon padding)

Spacing Tokens:
xs:   4px   (micro: text line height, icon gaps)
sm:   8px   (tight: margins, padding around text)
md:  16px   (standard: card padding, section spacing)
lg:  24px   (generous: section breaks, screen padding)
xl:  32px   (large: container margins, major breaks)
xxl: 48px   (extra-large: screen top padding, hero sections)
```

### Padding Standards

| Component | Vertical | Horizontal | Rationale |
|-----------|----------|-----------|-----------|
| **Screen/Container** | 16px | 16px | Standard mobile safe area |
| **Card (standard)** | 16px | 16px | Comfortable reading |
| **Card (compact)** | 12px | 12px | Data-dense tables |
| **Form Field** | 12px | 14px | Touch target height: 48px |
| **Button (primary)** | 12px | 20px | Touch target: 48x48px minimum |
| **List Item** | 12px | 16px | iPhone accessibility |
| **Section** | 24px | 16px | Visual separation |
| **Modal** | 20px | 20px | Dialog content breathing room |

### Margin Standards

| Context | Margin | Rationale |
|---------|--------|-----------|
| **Between cards** | 16px | Standard visual separation |
| **Between sections** | 24px | Major content break |
| **Top of screen** | 16px | Safe area below nav |
| **Bottom of screen** | 24px | Above bottom nav (80px total) |
| **Between list items** | 8px | Compact, scannable |
| **Icon to text** | 8px | Comfortable spacing |

### Breakpoints (Responsive)

```
Mobile (xs):    320px – 479px   (iPhone SE, small phones)
Mobile+ (sm):   480px – 639px   (iPhone 12–14)
Tablet (md):    640px – 1023px  (iPad, landscape)
Desktop (lg):   1024px – 1279px (iPad Pro, small screens)
Desktop+ (xl):  1280px+         (large screens)

iOS Safe Area Insets:
  Top:    44px (notched) or 20px (non-notched)
  Bottom: 34px (Face ID) or 20px (Touch ID)
  Left/Right: 0px (standard)
```

### Component Sizing

| Component | Height | Width Notes |
|-----------|--------|-------------|
| **Button (standard)** | 48px | Full-width or intrinsic |
| **Button (small)** | 40px | Compact actions |
| **Form Input** | 48px | Full-width, 16px padding |
| **Card** | Intrinsic | Full-width minus 16px padding |
| **Icon (small)** | 20px | Decorative, metadata |
| **Icon (standard)** | 24px | Navigation, buttons |
| **Icon (large)** | 32px | Hero sections, emphasis |
| **Metric Card** | 100px | Three columns per row (mobile) |
| **Chart Container** | 240px minimum | Data visualization area |

---

## Component Library

### Buttons

#### Primary Button

```
State: Default
  Background: #0A84FF (Sky Blue)
  Text: #FFFFFF (white)
  Text Style: Button Label (14px, 600)
  Padding: 12px vertical × 20px horizontal
  Border Radius: 8px
  Height: 48px minimum
  Shadow: None

State: Hover (web/desktop only)
  Background: #0066CC (darker blue)
  Text: #FFFFFF
  Cursor: pointer

State: Active/Pressed
  Background: #0052A3 (even darker)
  Transform: scale(0.98)
  Opacity: 0.95

State: Disabled
  Background: #D1D5DB (gray)
  Text: #9CA3AF (lighter gray)
  Opacity: 0.6
  Cursor: not-allowed

State: Loading
  Background: #0A84FF (same)
  Content: Spinner (12px, white) + "Loading..." text
  Disabled: true
```

#### Secondary Button

```
State: Default
  Background: #F3F4F6 (gray 100)
  Text: #1F2937 (navy)
  Text Style: Button Label (14px, 600)
  Padding: 12px × 20px
  Border: 1px solid #D1D5DB
  Border Radius: 8px
  Height: 48px

State: Hover
  Background: #E5E7EB (gray 200)
  Border: 1px solid #9CA3AF

State: Active/Pressed
  Background: #D1D5DB (gray 300)
  Transform: scale(0.98)

State: Disabled
  Background: #F9FAFB
  Text: #9CA3AF
  Border: 1px solid #D1D5DB
  Opacity: 0.5
```

#### Tertiary Button (Link-style)

```
State: Default
  Background: transparent
  Text: #0A84FF (sky blue)
  Text Style: Button Label (14px, 600)
  Padding: 12px × 8px (minimal)
  Border: none
  Height: 44px minimum (touch target)

State: Hover
  Text: #0052A3 (darker)
  Text-decoration: underline

State: Active/Pressed
  Text: #003D7A (darkest)
  Opacity: 0.8

State: Disabled
  Text: #9CA3AF (gray)
  Opacity: 0.5
```

#### Icon Button

```
State: Default
  Background: transparent
  Icon: 24px, #1F2937
  Padding: 12px (icon centered in 48×48px area)
  Border Radius: 8px
  Hit Area: 48×48px

State: Hover
  Background: #F3F4F6
  Icon: #0A84FF

State: Active/Pressed
  Background: #E5E7EB
  Icon: #0052A3
  Transform: scale(0.95)

State: Disabled
  Icon: #9CA3AF
  Opacity: 0.5
```

### Input Fields

#### Text Input (all types: text, email, password, number)

```
State: Default (Empty)
  Background: #FFFFFF
  Border: 1px solid #D1D5DB
  Border Radius: 8px
  Height: 48px
  Padding: 12px 14px
  Text: Body Small (14px, 400), #111827
  Placeholder: Body Small (14px, 400), #9CA3AF
  Icon (optional left): 20px, #6B7280, 8px left of text

State: Focused
  Border: 2px solid #0A84FF (sky blue)
  Box Shadow: 0 0 0 3px rgba(10, 132, 255, 0.1)
  Outline: none
  Background: #FFFFFF

State: Filled (with value)
  Border: 1px solid #D1D5DB
  Text: #111827
  Cursor: text

State: Error
  Border: 2px solid #EF4444
  Box Shadow: 0 0 0 3px rgba(239, 68, 68, 0.1)
  Error Icon: 20px, #EF4444, right side
  Error Text Below: Caption (12px, 500), #EF4444

State: Disabled
  Background: #F3F4F6
  Border: 1px solid #D1D5DB
  Text: #9CA3AF
  Cursor: not-allowed
  Opacity: 0.6

State: Success (optional validation)
  Border: 2px solid #10B981
  Box Shadow: 0 0 0 3px rgba(16, 185, 129, 0.1)
  Success Icon: 20px, #10B981, right side
```

#### Form Label & Hint Text

```
Label (above input):
  Text: Body Small (14px, 600), #111827
  Margin Bottom: 8px
  Required Indicator: "*" in #EF4444 (optional)

Hint Text (below input, always visible):
  Text: Caption (12px, 400), #6B7280
  Margin Top: 4px

Error Text (replaces hint, shows on error):
  Text: Caption (12px, 500), #EF4444
  Icon: Alert triangle, 12px, #EF4444
  Margin Top: 4px
```

### Cards

#### Standard Card

```
State: Default
  Background: #FFFFFF
  Border: 1px solid #E5E7EB
  Border Radius: 12px
  Padding: 16px
  Box Shadow: 0 1px 3px rgba(0, 0, 0, 0.1)
  Margin Bottom: 16px

State: Hover (interactive)
  Box Shadow: 0 4px 12px rgba(0, 0, 0, 0.15)
  Transform: translateY(-2px) (subtle lift)

State: Active/Selected
  Border: 2px solid #0A84FF
  Box Shadow: 0 4px 12px rgba(10, 132, 255, 0.2)
```

#### Metric Card (KPI display)

```
Layout: Vertical stack
  Label (top): Metric Label (11px, 600), #6B7280, margin-bottom 4px
  Value (center): Metric Value (24px, 700), color varies:
    - Positive: #10B981 (green)
    - Negative: #EF4444 (red)
    - Neutral: #1F2937 (navy)
  Status Badge (optional): 8px top margin

Background Options:
  Standard: #FFFFFF on #F3F4F6 container
  Success Tint: #F0FDFB (very light green)
  Warning Tint: #FFFBEB (very light orange)
  Error Tint: #FEF2F2 (very light red)
```

#### Data Card (table/list container)

```
Background: #FFFFFF
Border: 1px solid #E5E7EB
Border Radius: 12px
Padding: 16px
Column Headers:
  Text: Table Header (12px, 600), #6B7280
  Padding: 8px
  Border Bottom: 1px solid #E5E7EB

Row:
  Text: Table Cell (14px, 400), #111827
  Padding: 12px 8px
  Border Bottom: 1px solid #F3F4F6 (last row: none)
  Min Height: 40px
```

### Status Indicators & Badges

#### Status Badge

```
Success Badge:
  Background: #D1FAE5
  Text: #047857
  Border: 1px solid #A7F3D0
  Padding: 4px 8px
  Border Radius: 20px
  Text Style: Caption (11px, 500)
  Icon (optional): 12px checkmark

Warning Badge:
  Background: #FEF3C7
  Text: #B45309
  Border: 1px solid #FECB45
  Padding: 4px 8px
  Border Radius: 20px

Error Badge:
  Background: #FEE2E2
  Text: #991B1B
  Border: 1px solid #FCBDBD
  Padding: 4px 8px
  Border Radius: 20px

Info Badge:
  Background: #DBEAFE
  Text: #1E40AF
  Border: 1px solid #93C5FD
  Padding: 4px 8px
  Border Radius: 20px
```

#### Inline Status Indicators

```
Dot Indicator (no text):
  Size: 8px diameter
  Border Radius: 50%
  Color: varies by status (green/orange/red/blue)
  Margin Right: 8px

Status Text + Dot:
  Format: "● Status Name"
  Text: Body Small (14px, 400)
  Color: text matches dot color
```

### Charts & Visualizations

#### Line Chart Container

```
Container:
  Background: #F3F4F6
  Border Radius: 12px
  Padding: 16px
  Min Height: 240px
  Border: 1px solid #E5E7EB

Axes:
  Text: Caption (12px, 400), #6B7280
  Lines: 1px solid #E5E7EB
  Padding: 16px

Grid:
  Color: #E5E7EB
  Style: subtle (0.5px opacity)

Legend:
  Position: Top-right
  Layout: horizontal, chips
  Text: Caption (12px, 400)
  Dot: 8px circle + text

Line (data series):
  Width: 2px
  Color: per chart color palette
  Curve: smooth (bezier)

Point (data dot):
  Size: 4px diameter
  Color: line color
  Hover: 6px, add shadow
```

#### Bar Chart Container

```
Same as line chart, but:

Bar:
  Width: calculated per count
  Max width: 40px per bar
  Min width: 8px
  Color: per chart color palette
  Border Radius: 4px (top only)
  Spacing: 4px between bars

Stacked Bar (cost breakdown):
  Segments: multiple colors stacked
  Colors: per category (turbine, O&M, etc.)
  Label: on hover or sidebar legend
```

### Alert & Notification Components

#### Banner Alert

```
Background: varies by severity
  Info: #DBEAFE
  Warning: #FEF3C7
  Error: #FEE2E2
  Success: #D1FAE5

Border Left: 4px solid (matches type color)
Padding: 12px 16px
Border Radius: 8px
Margin Bottom: 16px

Layout:
  Icon (left): 20px, matches type color
  Text (center): Body Small (14px, 400), type color text
  Close Button (right): X icon, transparent background

State: Dismissible
  Close icon appears on hover/focus
  Removing: fade out 200ms
```

#### Toast Notification (temporary)

```
Position: Bottom-center or top-right
Background: #1F2937 (navy)
Text: #FFFFFF (white)
Padding: 16px
Border Radius: 8px
Box Shadow: 0 10px 25px rgba(0, 0, 0, 0.2)
Min Width: 280px
Max Width: 420px

Auto-dismiss: 3-4 seconds (unless persistent)
Animation: slide-up + fade-in on enter
          slide-down + fade-out on exit
Duration: 200ms
```

### Navigation Components

#### Bottom Navigation (iOS Tab Bar style)

```
Position: Fixed bottom
Height: 80px total (includes 20px safe area on iPhone)
Background: #FFFFFF
Border Top: 1px solid #E5E7EB
Display: Flex, space-around

Per Tab:
  Width: Equal distribution (5 tabs = 20% each)
  Padding: 12px 0 (8px minimum)
  Touch Area: 48×48px minimum

Inactive Tab:
  Icon: 24px, #6B7280
  Label: Tab Label (13px, 600), #6B7280
  Spacing: 4px between icon and label

Active Tab:
  Icon: 24px, #0A84FF
  Label: Tab Label (13px, 600), #0A84FF
  Indicator (optional): 2px line above tab

Ripple Effect (Android):
  Background fade: 0.1s
  Color: #0A84FF at 12% opacity
```

#### Top Navigation Bar

```
Height: 56px
Background: #1F2937 (navy)
Content Padding: 0 16px

Left Section:
  Back Button: 24px icon, white
  OR Logo: 24px, white

Center Section:
  Title: Header/Title (28px, 700), white
  Alignment: center or left-aligned

Right Section:
  Action Buttons: 24px icons, white
  Spacing: 16px between buttons

Safe Area: Respect top notch/status bar
```

### Modals & Bottom Sheets

#### Modal Dialog

```
Overlay:
  Background: rgba(0, 0, 0, 0.5)
  Dismiss on tap: yes

Modal Container:
  Background: #FFFFFF
  Border Radius: 16px
  Padding: 24px
  Max Width: 90vw or 500px
  Animation: Scale + fade in (200ms ease-out)

Header:
  Title: Header/Title (28px, 700)
  Close Button (optional): X icon, top-right

Body:
  Content: Standard spacing, form fields, etc.
  Max Height: 80vh (scrollable if needed)

Footer:
  Buttons: Usually primary + secondary
  Spacing: 8px between
  Margin Top: 24px
```

#### Bottom Sheet (Material Design style)

```
Position: Slides up from bottom
Background: #FFFFFF
Border Radius: 16px (top corners only)
Padding: 20px 16px

Handle (Android Material):
  Visual: 4px × 32px rounded bar
  Position: Top center, 8px from top
  Color: #D1D5DB
  Touch target: Full width, top 20px

Content:
  Same as modal body
  Dismiss: Swipe down or tap outside
  Animation: Slide up (250ms), slide down (200ms)

Safe Area:
  Respect bottom safe area (iPhone Face ID)
```

### Form Components

#### Checkbox

```
Size: 20px × 20px
Border: 2px solid #D1D5DB
Border Radius: 4px
Background (unchecked): #FFFFFF

State: Checked
  Background: #0A84FF
  Border: 2px solid #0A84FF
  Icon: White checkmark (12px, 2px stroke)

State: Focused
  Box Shadow: 0 0 0 3px rgba(10, 132, 255, 0.2)

State: Disabled
  Background: #F3F4F6
  Border: 2px solid #D1D5DB
  Opacity: 0.6

Label (adjacent text):
  Margin Left: 8px
  Text: Body Small (14px, 400)
  Touch target: Extends to text
```

#### Radio Button

```
Size: 20px × 20px
Border: 2px solid #D1D5DB
Border Radius: 50%
Background (unchecked): #FFFFFF

State: Checked
  Border: 2px solid #0A84FF
  Inner dot: 8px diameter, #0A84FF
  Animation: dot appears (100ms)

State: Focused
  Box Shadow: 0 0 0 3px rgba(10, 132, 255, 0.2)

State: Disabled
  Border: 2px solid #D1D5DB
  Background: #F3F4F6
  Opacity: 0.6

Label: Same as checkbox
```

#### Toggle Switch

```
Width: 48px
Height: 28px
Border Radius: 14px
Background (off): #D1D5DB
Padding: 2px

State: On
  Background: #0A84FF
  Knob: 24px diameter, #FFFFFF, positioned right
  Animation: Knob slides right (200ms ease-out)

State: Off
  Knob: positioned left

State: Focused
  Box Shadow: 0 0 0 3px rgba(10, 132, 255, 0.2)

State: Disabled
  Background: #E5E7EB
  Opacity: 0.5
  Cursor: not-allowed
```

#### Select Dropdown

```
Height: 48px
Background: #FFFFFF
Border: 1px solid #D1D5DB
Border Radius: 8px
Padding: 12px 14px
Text: Body Small (14px, 400), #111827

State: Focused
  Border: 2px solid #0A84FF
  Box Shadow: 0 0 0 3px rgba(10, 132, 255, 0.1)

State: Open
  Border: 2px solid #0A84FF
  Background: #FFFFFF
  Icon (right): Chevron up

Dropdown Menu:
  Position: Below or above input (auto)
  Background: #FFFFFF
  Border: 1px solid #E5E7EB
  Border Radius: 8px
  Box Shadow: 0 4px 12px rgba(0, 0, 0, 0.15)
  Z-index: 1000

Menu Item:
  Padding: 12px 14px
  Text: Body Small (14px, 400)
  Min Height: 40px
  Background (default): #FFFFFF
  Background (hover): #F3F4F6
  Background (selected): #E0F1FF
  Text (selected): #0A84FF

Scroll (if needed):
  Max Height: 200px
  Scrollbar: thin, gray
```

---

## Interactive States

### General State Machine

All components follow this state hierarchy:

```
Default → Hover → Active/Pressed → Disabled
               ↓
           Focused (keyboard/touch)
               ↓
          Error (validation)
               ↓
          Loading (async)
               ↓
          Success (feedback)
```

### Timing & Animation

| Action | Duration | Easing | Usage |
|--------|----------|--------|-------|
| Hover state change | 150ms | ease-out | Button hover, card lift |
| Press/active | 50ms | ease-out | Immediate feedback |
| Tap ripple (Android) | 400ms | ease-out | Material ripple effect |
| Transition (view) | 250ms | ease-out | Screen navigation |
| Fade (dismiss) | 200ms | ease-out | Alert/toast dismiss |
| Bounce (emphasis) | 200ms | ease-in-out | Success feedback |
| Loader spin | 1s | linear | Loading indicator |

### Focus Indicators (Accessibility)

```
Keyboard Focus (all interactive elements):
  Ring: 2px solid #0A84FF outline
  Offset: 2px from element edge
  Always visible (never remove)

Touch Focus (mobile):
  Background: slight background shift
  Ring: optional (if button not text-intensive)

Focus-visible (CSS):
  Use :focus-visible for keyboard only
  Use :focus for all interactions on mobile
```

### Error States

```
Field Error:
  Border: 2px solid #EF4444
  Icon: Alert icon (20px, right side)
  Text: Error message below (Caption, #EF4444)
  Focus still allowed: Border changes to 2px #EF4444

Submission Error:
  Banner: Full-width error alert at top
  Clear trigger: On form edit/resubmit
  Duration: Persistent until resolved

Validation Error (real-time):
  Appears after blur or delay (500ms typing)
  Dismisses on valid input
  Helpful message: "Must be at least 8 characters"
```

### Loading States

```
Button Loading:
  Content: Replace text with spinner
  Spinner: 16px diameter, 2px stroke
  Color: white (if primary button)
  Text: "Loading..." (optional)
  Disabled: true (can't re-trigger)
  Duration: Until request completes

Page Loading:
  Skeleton screens preferred over spinner
  Show placeholder cards in gray (#E5E7EB)
  Animate pulse: opacity 0.5 → 1.0 → 0.5 (1.5s)
  Replace with actual content (no flash)

Data Loading:
  Inline spinner: 20px, within card
  Text: "Loading data..." (optional)
  Timeout: Show error after 10s
```

### Success States

```
After Form Submission:
  Success toast: Slide up from bottom
  Message: "✓ Saved successfully"
  Duration: 3 seconds, auto-dismiss
  Icon: Checkmark (20px, #10B981)
  Color: #D1FAE5 background, #047857 text

After Data Action:
  Brief feedback: Icon change or color shift
  Duration: 1–2 seconds
  Animation: Scale-up (120%) then shrink back
```

---

## Dark Mode

### Dark Color Palette

| Element | Light | Dark | Notes |
|---------|-------|------|-------|
| **Background** | #FFFFFF | #111827 | Primary surface |
| **Surface Secondary** | #F9FAFB | #1F2937 | Cards, panels |
| **Text Primary** | #111827 | #FFFFFF | Main text |
| **Text Secondary** | #6B7280 | #D1D5DB | Hints, secondary |
| **Border** | #D1D5DB | #374151 | Dividers, edges |
| **Primary Brand** | #0A84FF | #60A5FA | Lighter for contrast on dark |
| **Navy Header** | #1F2937 | #0F172A | Darker for dark mode |
| **Success** | #10B981 | #34D399 | Brighter for dark |
| **Warning** | #F59E0B | #FCD34D | Brighter for dark |
| **Danger** | #EF4444 | #F87171 | Brighter for dark |
| **Chart Bg** | #F3F4F6 | #1F2937 | Dark container |

### Dark Mode Implementation

```
CSS Variables Approach:

:root {
  --color-bg-primary: #FFFFFF;
  --color-text-primary: #111827;
  --color-border: #D1D5DB;
  /* ... etc */
}

@media (prefers-color-scheme: dark) {
  :root {
    --color-bg-primary: #111827;
    --color-text-primary: #FFFFFF;
    --color-border: #374151;
    /* ... etc */
  }
}

Or use data attribute:
[data-theme="dark"] {
  --color-bg-primary: #111827;
  /* ... */
}
```

### Dark Mode Contrast Requirements

All WCAG AA minimum ratios maintained:
- Text on dark background must be brighter
- Chart colors must increase saturation (+20% lightness)
- Borders must be lighter (#374151+)
- Shadows reduced or removed (dark bg already provides contrast)

---

## Accessibility

### WCAG 2.1 AA Compliance Checklist

- [ ] **Color Contrast:** All text ≥4.5:1 (normal), ≥3:1 (large)
- [ ] **Color Not Sole Indicator:** Use icons + text or labels
- [ ] **Focus Indicators:** Always visible, ≥3:1 contrast
- [ ] **Keyboard Navigation:** All interactive elements reachable via Tab
- [ ] **Form Labels:** Explicit labels for all inputs (not placeholder-only)
- [ ] **Error Messages:** Clear, specific, actionable
- [ ] **Images:** Meaningful alt text on icons/images
- [ ] **Animations:** Respect prefers-reduced-motion
- [ ] **Touch Targets:** Minimum 48×48px (iOS 44×44pt acceptable)
- [ ] **Semantic HTML:** Proper heading hierarchy, lists, buttons

### Semantic Markup

```html
<!-- Button (not <div>): -->
<button type="button">Save</button>

<!-- Form Control (not <div>): -->
<input type="email" aria-label="Email address" />

<!-- Heading Hierarchy (never skip levels): -->
<h1>Dashboard</h1>
<h2>Financial Metrics</h2>
<h3>NPV Analysis</h3>

<!-- List (not pseudo-list): -->
<ul role="list">
  <li>Item 1</li>
  <li>Item 2</li>
</ul>

<!-- ARIA for complex components: -->
<div role="tablist">
  <button role="tab" aria-selected="true">Tab 1</button>
  <button role="tab" aria-selected="false">Tab 2</button>
</div>
```

### Screen Reader Considerations

```
Hidden from Screen Readers (decorative elements):
  aria-hidden="true"
  Example: <span aria-hidden="true">→</span>

Accessible Name (for icons):
  aria-label="Go to next page"
  Example: <button aria-label="Settings"><Gear /></button>

Descriptions (complex info):
  aria-describedby="hint-text"
  Example: <input aria-describedby="pwd-hint" />
           <span id="pwd-hint">Min 8 characters</span>

Live Regions (dynamic updates):
  aria-live="polite" (wait for pause)
  aria-live="assertive" (interrupt)
  Example: <div aria-live="polite">Data updated</div>
```

### Color Blindness Considerations

- **Protanopia (red-blind):** Avoid red-only indicators; pair with icons/text
- **Deuteranopia (green-blind):** Avoid green-only signals
- **Tritanopia (blue-yellow-blind):** Use red-green or black-white contrasts for critical info

**Solution:** Always combine color with shape/icon/text label.

### Motion & Animation

```
Respect prefers-reduced-motion:

@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

Exceptions: Keep focus indicators, hover states (not animated)
```

---

## Micro-interactions

### Feedback Patterns

#### Button Press Feedback

```
Sequence:
1. Press: Scale down 2% (98% size), darken 10%
2. Duration: 50ms
3. Release: Spring back (150ms, ease-out)
4. Ripple (Android): 400ms from tap point, 0.1 opacity

Code:
button:active {
  transform: scale(0.98);
  background-color: darker();
  transition: transform 50ms ease-out;
}
```

#### Form Validation Feedback

```
Real-time Validation:
1. User types in email field
2. After 500ms pause (or blur): validate
3. Invalid: shake animation (100ms) + error text appears
4. Valid: Green checkmark slides in (200ms)

Shake Animation:
  @keyframes shake {
    0%, 100% { transform: translateX(0); }
    25% { transform: translateX(-8px); }
    75% { transform: translateX(8px); }
  }
  Duration: 100ms
```

#### Card Tap Response

```
Interactive card (table row, scenario card):
1. Press: Add shadow, background tint
2. Duration: Immediate
3. Hold: Maintain state
4. Release: Fade out shadow (200ms)
5. Navigation: If tappable, navigate after brief delay (100ms)
```

#### Toast Notification

```
Entrance:
  Start: translateY(100px) opacity 0
  End: translateY(0) opacity 1
  Duration: 200ms ease-out
  Timing: Stagger if multiple (100ms offset)

Display: 3-4 seconds (auto-dismiss)

Exit:
  Start: translateY(0) opacity 1
  End: translateY(100px) opacity 0
  Duration: 200ms ease-out
  Trigger: User swipe up or timeout
```

#### List Item Swipe (if applicable)

```
Swipe Right (approve/complete):
  1. Swipe detector: 50px minimum distance
  2. Visual: Reveal green action button
  3. Threshold: 50% of width triggers action
  4. Completion: Fade out + slide left (200ms)

Swipe Left (delete/archive):
  Same pattern, red button, swipe left
```

### Empty States

#### Skeleton Screens (loading)

```
Layout: Mirror actual content structure
Cards: 200px height, gray (#E5E7EB)
Animation: Pulse opacity (0.5 → 1.0 → 0.5) over 1.5s
Timing: Stagger children by 100ms
Swap: Fade out skeleton, fade in real content (200ms)
```

#### Empty State Illustrations (no data)

```
Image: Center-aligned, 120×120px, gray (#9CA3AF)
Title: "No data available" (Section Title, #6B7280)
Message: "Add your first scenario to get started." (Body Small)
CTA: Primary button "Create Scenario"
Spacing: 24px between elements
```

### Accessibility + Micro-interactions

```
Avoid motion sickness triggers:
  • Max parallax: 3-5px only
  • Avoid vestibular motion (spinning, tilting)
  • Duration: Keep transitions <500ms

Respect user preference:
  if (prefersReducedMotion) {
    transitionDuration = "0.01ms";
    animationDuration = "0.01ms";
  }
```

---

## iOS/Android Adaptations

### Unified Approach (Option A – Recommended for MVP)

#### Font Adjustments

```
iOS:
  Font: Inter (system fallback: SF Pro)
  Line Height: Tight (current specs)
  Weight: Exact (400, 600, 700)

Android:
  Font: Inter (system fallback: Roboto)
  Line Height: +2px on body copy for legibility
  Weight: Same (Android will render slightly bolder)
```

#### Spacing Adjustments

```
iOS:
  Card padding: 16px
  Touch targets: 44×44pt minimum

Android:
  Card padding: 16px (same)
  Touch targets: 48×48dp (larger, Material standard)

Shared:
  8px grid system (both platforms use it)
  Section margins: 24px (both)
```

#### Bottom Navigation (Platform-Specific UI)

**iOS Tab Bar:**
```
Height: 80px (includes safe area)
Icons: 24px
Labels: 13px, 600 weight
Background: White, top border 1px gray
Active indicator: 2px line above (or color change)
Ripple: None (not iOS pattern)
```

**Android Bottom Navigation:**
```
Height: 80px (Material standard includes padding)
Icons: 24px
Labels: 12px (slightly smaller)
Background: White
Active indicator: Color change + optional line
Ripple: Material ripple (12% opacity)
Shape (Material 3): Optional rounded container
```

#### Corner Radius

```
iOS (current):
  Buttons: 8px
  Cards: 12px
  Modals: 16px

Android Material 3:
  Buttons: 8–12px (slightly rounder)
  Cards: 12px (same)
  Modals: 16–28px (more prominent)

Recommendation: Use 12px standard, 16px modals
(Slightly rounder for both, no conflict)
```

#### Shadows

```
iOS:
  Subtle, minimal
  (System handles platform shadow)

Android:
  Material elevation system
  Shadow scales with elevation (1–24dp)
  Sharper shadows, more defined

Unified Approach:
  Use CSS shadows that work on both:
  0 2px 4px rgba(0,0,0,0.1)   (subtle)
  0 4px 12px rgba(0,0,0,0.15) (card lift)
  Android will render slightly sharper
```

#### Buttons (Native Affordance)

```
iOS:
  Style: Current primary/secondary buttons
  Feedback: Scale + color (no ripple)

Android:
  Style: Same buttons visually
  Feedback: Add Material ripple for extra feedback
  Shape: Slightly rounder (12px vs 8px OK)

Code Implementation:
  <button class="btn btn--primary">
    <!-- Both platforms render similarly -->
    <!-- Android adds ripple effect via JS/CSS -->
  </button>

Android-Specific CSS (optional):
  .btn::after {
    /* Ripple element */
    position: absolute;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.3);
    animation: ripple 400ms ease-out;
  }
```

### Data Density Considerations

```
iOS (prefer spacious):
  List item height: 56–64px
  Padding: 16px horizontal

Android (can be dense):
  List item height: 48–52px
  Padding: 16px horizontal (same for accessibility)

Compromise:
  Use 56px height (accommodates both, accessible)
  Consistent spacing (16px)
```

### Input Method Differences

```
iOS:
  Keyboard: Context-aware (email, phone, etc.)
  Dismiss: Keyboard button or tap outside
  Safe area: Respects input area (no overlap)

Android:
  Keyboard: Similar context-aware
  Dismiss: Back gesture or outside tap
  Safe area: Handle bottom inset

Handling:
  Use <input type="email"> for both
  CSS: input { padding-bottom: 8px; } (extra space)
  Scroll: Auto-scroll input into view on focus (native)
```

---

## Changelog & Version History

| Version | Date | Changes |
|---------|------|---------|
| **v1.0** | Dec 2025 | Initial design system complete |
| **v1.1** | TBD | Dark mode refinement |
| **v1.2** | TBD | Android Material 3 components |
| **v2.0** | TBD | Web layout system (1024px+) |

---

## References & Tools

- **Design Tool:** Figma (see Component Library document)
- **Font:** Inter (Google Fonts, OFL License)
- **Accessibility:** WCAG 2.1 AA
- **iOS Guidelines:** Apple Human Interface Guidelines (iOS 17+)
- **Android Guidelines:** Material Design 3
- **Color Contrast:** WebAIM Contrast Checker
- **Testing:** axe DevTools, NVDA, JAWS

---

**Document Owner:** Design Team
**Last Reviewed:** December 2025
**Next Review:** March 2026
