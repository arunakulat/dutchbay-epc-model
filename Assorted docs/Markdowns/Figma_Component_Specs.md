# Figma Component Template Specifications

**Dutch Bay EPC Design System – Layer Structure & Variants**

Version 1.0.0 | December 2025

---

## Table of Contents

1. [Button Components](#button-components)
2. [Card Components](#card-components)
3. [Input Components](#input-components)
4. [Badge Components](#badge-components)
5. [Navigation Components](#navigation-components)
6. [Layer Naming Convention](#layer-naming-convention)
7. [Variant Property Setup](#variant-property-setup)

---

## Button Components

### Button/Primary

**Master Component Properties:**
```
Name: Button/Primary
Frame Size: 48px (H) × variable (W)
Auto Layout: ON
Direction: Horizontal
Spacing: 0px
Padding: 12px (vertical) × 20px (horizontal)
Border Radius: 8px
```

**Layer Structure:**
```
Button/Primary (COMPONENT)
├── BG (Rectangle)
│   ├── Fill: #0A84FF
│   ├── Stroke: None
│   └── Border Radius: 8px
├── Label (Text)
│   ├── Text: "Button Text"
│   ├── Font: Inter
│   ├── Font Size: 14px
│   ├── Font Weight: 600
│   ├── Line Height: 20px
│   ├── Color: #FFFFFF
│   └── Alignment: Center
└── Icon (Optional Group) [OPTIONAL]
    ├── Icon (Icon Component)
    └── Spacing: 8px from label
```

**Variant Properties:**

| Property | Values | Style Changes |
|----------|--------|---------------|
| **State** | Default, Hover, Active, Disabled | Background color |
| **Size** | Small, Medium, Large | Height: 40px, 48px, 56px |
| **Icon** | True, False | Show/hide icon layer |

**Variant Specifications:**

**State=Default**
- BG Fill: #0A84FF
- Label Color: #FFFFFF
- Shadow: None

**State=Hover**
- BG Fill: #0066CC
- Label Color: #FFFFFF
- Shadow: var(--shadow-subtle)

**State=Active**
- BG Fill: #0052A3
- Label Color: #FFFFFF
- Opacity: 95%

**State=Disabled**
- BG Fill: #E5E7EB
- Label Color: #9CA3AF
- Opacity: 60%
- Pointer Events: None

**Size=Small**
- Frame Height: 40px
- Padding: 8px (vertical) × 12px (horizontal)
- Font Size: 12px

**Size=Medium** (default)
- Frame Height: 48px
- Padding: 12px × 20px
- Font Size: 14px

**Size=Large**
- Frame Height: 56px
- Padding: 16px × 24px
- Font Size: 16px

---

### Button/Secondary

**Master Component Properties:**
```
Name: Button/Secondary
Frame Size: 48px (H) × variable (W)
Auto Layout: ON
Direction: Horizontal
Spacing: 0px
Padding: 12px (vertical) × 20px (horizontal)
Border Radius: 8px
```

**Layer Structure:**
```
Button/Secondary (COMPONENT)
├── BG (Rectangle)
│   ├── Fill: #F3F4F6
│   ├── Stroke: 1px solid #D1D5DB
│   └── Border Radius: 8px
├── Label (Text)
│   ├── Text: "Button Text"
│   ├── Font: Inter
│   ├── Font Size: 14px
│   ├── Font Weight: 600
│   ├── Line Height: 20px
│   ├── Color: #1F2937
│   └── Alignment: Center
└── Icon (Optional Group) [OPTIONAL]
    └── Icon (Icon Component)
```

**Variant Properties:**

| Property | Values |
|----------|--------|
| **State** | Default, Hover, Disabled |
| **Size** | Small, Medium, Large |

**Variant Specifications:**

**State=Default**
- BG Fill: #F3F4F6
- Border: 1px #D1D5DB
- Label Color: #1F2937

**State=Hover**
- BG Fill: #E5E7EB
- Border: 1px #9CA3AF
- Label Color: #1F2937

**State=Disabled**
- BG Fill: #F3F4F6
- Border: 1px #D1D5DB
- Label Color: #9CA3AF
- Opacity: 60%

---

## Card Components

### Card/Standard

**Master Component Properties:**
```
Name: Card/Standard
Frame Size: 360px (W) × auto (H)
Auto Layout: ON
Direction: Vertical
Spacing: 0px
Padding: 16px
```

**Layer Structure:**
```
Card/Standard (COMPONENT)
├── BG (Rectangle)
│   ├── Fill: #FFFFFF
│   ├── Stroke: 1px solid #E5E7EB
│   ├── Border Radius: 12px
│   └── Shadow: 0 1px 3px rgba(0,0,0,0.1)
├── Content (Frame/Group)
│   ├── Auto Layout: Vertical, spacing 12px
│   ├── Title (Text) [OPTIONAL]
│   │   ├── Font Size: 18px
│   │   ├── Font Weight: 600
│   │   ├── Color: #1F2937
│   │   └── Margin Bottom: 8px
│   ├── Subtitle (Text) [OPTIONAL]
│   │   ├── Font Size: 14px
│   │   ├── Font Weight: 400
│   │   ├── Color: #6B7280
│   │   └── Margin Bottom: 4px
│   └── Body Content (Placeholder) [REQUIRED]
│       └── Min Height: 60px (adjust per content)
```

**Variant Properties:**

| Property | Values |
|----------|--------|
| **Type** | Standard, Header, Body |
| **HasTitle** | True, False |
| **HasSubtitle** | True, False |

**Variant Specifications:**

**Type=Standard**
- All layers visible
- BG Fill: #FFFFFF
- Border: 1px #E5E7EB

**Type=Header**
- Hide: Content > Body
- Show: Content > Title, Subtitle
- Border Bottom: 1px #E5E7EB on Title
- Padding Bottom: 12px on Title

**Type=Body**
- Hide: Content > Title, Subtitle
- Show: Content > Body only
- Padding Top: 0px

---

### Card/Metric

**Master Component Properties:**
```
Name: Card/Metric
Frame Size: 100px (W) × 140px (H)
Auto Layout: ON
Direction: Vertical
Spacing: 8px
Padding: 16px
```

**Layer Structure:**
```
Card/Metric (COMPONENT)
├── BG (Rectangle)
│   ├── Fill: #FFFFFF
│   ├── Stroke: 1px solid #E5E7EB
│   ├── Border Radius: 12px
│   └── Shadow: 0 1px 3px rgba(0,0,0,0.1)
├── Label (Text)
│   ├── Text: "NPV"
│   ├── Font: Inter
│   ├── Font Size: 11px
│   ├── Font Weight: 600
│   ├── Letter Spacing: 0.3px
│   ├── Line Height: 14px
│   ├── Color: #6B7280
│   └── Text Transform: Uppercase
├── Value (Text)
│   ├── Text: "$45.2M"
│   ├── Font: IBM Plex Mono
│   ├── Font Size: 24px
│   ├── Font Weight: 700
│   ├── Line Height: 32px
│   ├── Letter Spacing: -0.3px
│   └── Color: Varies by variant
└── Badge (Component Instance)
    ├── Type: Badge/Success
    ├── Size: Small
    └── Margin Top: 4px
```

**Variant Properties:**

| Property | Values | Style Changes |
|----------|--------|---------------|
| **Trend** | Positive, Negative, Neutral | BG Color, Value Color |
| **BadgeType** | Success, Warning, Danger, None | Badge color |

**Variant Specifications:**

**Trend=Positive**
- BG Fill: #F0FDFB
- BG Border: 1px #10B981
- Value Color: #10B981
- Badge: Success

**Trend=Negative**
- BG Fill: #FEF2F2
- BG Border: 1px #EF4444
- Value Color: #EF4444
- Badge: Danger

**Trend=Neutral**
- BG Fill: #FFFFFF
- BG Border: 1px #E5E7EB
- Value Color: #1F2937
- Badge: None

---

## Input Components

### Input/Text

**Master Component Properties:**
```
Name: Input/Text
Frame Size: variable (W) × 48px (H)
Auto Layout: OFF
```

**Layer Structure:**
```
Input/Text (COMPONENT)
├── BG (Rectangle)
│   ├── Fill: #FFFFFF
│   ├── Stroke: 1px solid #D1D5DB
│   ├── Border Radius: 8px
│   └── Padding: 12px 14px
├── Label (Text) [OPTIONAL]
│   ├── Font Size: 12px
│   ├── Font Weight: 600
│   ├── Color: #111827
│   └── Margin Bottom: 8px
├── Input Field (Text)
│   ├── Text: "Placeholder text"
│   ├── Font Size: 14px
│   ├── Font Weight: 400
│   ├── Color: #111827
│   ├── Placeholder Color: #9CA3AF
│   └── Line Height: 20px
└── Error Message (Text) [OPTIONAL]
    ├── Font Size: 12px
    ├── Color: #EF4444
    └── Margin Top: 4px
```

**Variant Properties:**

| Property | Values | Style Changes |
|----------|--------|---------------|
| **State** | Default, Focused, Error, Success | Border, Shadow |
| **Size** | Small, Medium, Large | Height: 40px, 48px, 56px |
| **HasLabel** | True, False | Show/hide label layer |
| **HasError** | True, False | Show/hide error message |

**Variant Specifications:**

**State=Default**
- Border: 1px #D1D5DB
- Shadow: None
- BG: #FFFFFF

**State=Focused**
- Border: 2px #0A84FF
- Shadow: 0 0 0 3px rgba(10, 132, 255, 0.1)
- BG: #FFFFFF

**State=Error**
- Border: 2px #EF4444
- BG: #FEF2F2
- Error Message: Visible

**State=Success**
- Border: 2px #10B981
- BG: #F0FDFB
- Checkmark: Visible

**Size=Small**
- Height: 40px
- Padding: 8px 12px
- Font Size: 12px

**Size=Medium** (default)
- Height: 48px
- Padding: 12px 14px
- Font Size: 14px

**Size=Large**
- Height: 56px
- Padding: 14px 16px
- Font Size: 16px

---

## Badge Components

### Badge/Success

**Master Component Properties:**
```
Name: Badge/Success
Frame Size: variable (W) × 24px (H)
Auto Layout: ON
Direction: Horizontal
Padding: 4px 8px
```

**Layer Structure:**
```
Badge/Success (COMPONENT)
├── BG (Rectangle)
│   ├── Fill: #D1FAE5
│   ├── Stroke: 1px solid #A7F3D0
│   └── Border Radius: 20px
└── Label (Text)
    ├── Text: "Healthy"
    ├── Font: Inter
    ├── Font Size: 11px
    ├── Font Weight: 500
    ├── Color: #047857
    └── Alignment: Center
```

**No Variants** – Use same structure for all badge types

---

### Badge/Warning

```
Name: Badge/Warning
├── BG Fill: #FEF3C7
├── BG Stroke: 1px solid #FECB45
└── Label Color: #B45309
```

---

### Badge/Danger

```
Name: Badge/Danger
├── BG Fill: #FEE2E2
├── BG Stroke: 1px solid #FCBDBD
└── Label Color: #991B1B
```

---

## Navigation Components

### NavTop

**Master Component Properties:**
```
Name: NavTop
Frame Size: 375px (W) × 56px (H)
Auto Layout: ON
Direction: Horizontal
Justify: Space Between
Align: Center
Padding: 0px 16px
```

**Layer Structure:**
```
NavTop (COMPONENT)
├── BG (Rectangle)
│   ├── Fill: #1F2937
│   ├── Stroke: None
│   └── Height: 56px
├── Left Content (Group)
│   └── Title (Text)
│       ├── Font Size: 28px
│       ├── Font Weight: 700
│       ├── Color: #FFFFFF
│       └── Text: "Dashboard"
└── Right Content (Group)
    └── Icon Button (Component Instance)
        └── Icon: ⚙️ or similar
```

---

### NavBottom

**Master Component Properties:**
```
Name: NavBottom
Frame Size: 375px (W) × 80px (H)
Auto Layout: ON
Direction: Horizontal
Justify: Space Around
Align: Flex End
Padding: 0px 0px 16px 0px
```

**Layer Structure:**
```
NavBottom (COMPONENT)
├── BG (Rectangle)
│   ├── Fill: #FFFFFF
│   ├── Stroke: 1px solid #E5E7EB
│   ├── Stroke Position: Top
│   └── Height: 80px
├── NavItem Dashboard (Group) [ACTIVE]
│   ├── Icon (Text): 📊
│   │   ├── Font Size: 24px
│   │   └── Color: #0A84FF
│   ├── Label (Text): Dashboard
│   │   ├── Font Size: 11px
│   │   ├── Font Weight: 600
│   │   ├── Color: #0A84FF
│   │   └── Margin Top: 4px
│   └── Spacing: 4px between icon & label
├── NavItem Scenarios (Group) [INACTIVE]
│   ├── Icon (Text): 🎯
│   │   ├── Font Size: 24px
│   │   └── Color: #9CA3AF
│   ├── Label (Text): Scenarios
│   │   ├── Font Size: 11px
│   │   ├── Font Weight: 600
│   │   ├── Color: #9CA3AF
│   │   └── Margin Top: 4px
│   └── Spacing: 4px
├── NavItem Metrics (Group)
│   └── [Same structure as Scenarios]
├── NavItem Reports (Group)
│   └── [Same structure as Scenarios]
└── NavItem Settings (Group)
    └── [Same structure as Scenarios]
```

**Variant Properties:**

| Property | Values |
|----------|--------|
| **Active** | Dashboard, Scenarios, Metrics, Reports, Settings |

**Each variant changes:**
- Which NavItem has color #0A84FF (active)
- Other NavItems have color #9CA3AF (inactive)

---

## Layer Naming Convention

### Naming Rules

Follow this naming pattern for consistency:

**Component Names:**
```
ComponentType/Variant/State
Example: Button/Primary/Default
         Card/Metric/Positive
         Input/Text/Focused
```

**Layer Names (inside components):**
```
[FunctionRole]_[Property]
Example: BG_Rectangle (background)
         Label_Text (label)
         Icon_Button (icon button)
         Content_Container (content wrapper)
```

**Instance Names (when used on screens):**
```
[ComponentType]_[Location]_[Context]
Example: Button_Dashboard_SaveChanges
         Card_Dashboard_NPVMetric
         NavBottom_AllScreens
```

### Color Names in Figma

Use semantic naming:
```
Primary/Navy (not "Dark Blue")
Primary/Sky (not "Light Blue")
Status/Success (not "Green")
Status/Warning (not "Orange")
Status/Danger (not "Red")
Neutral/Gray 100 (not "Light Gray")
```

---

## Variant Property Setup

### How to Create Variants in Figma

**Step 1: Create Base Component**
1. Design the component at actual size
2. Right-click → "Create component"
3. Name it with forward slashes: `Button/Primary`

**Step 2: Add Variant Properties**
1. Select component
2. Right side panel → "Component"
3. Click "Add property"
4. Name: `State`
5. Type: `Variant`
6. Values: `Default, Hover, Active, Disabled`

**Step 3: Create Variant Combinations**
1. Right-click component → "Create variants"
2. Add another property: `Size`
3. Values: `Small, Medium, Large`
4. This creates 4 × 3 = 12 total variants

**Step 4: Modify Each Variant**
1. Click into variant (e.g., "State=Hover")
2. Change appearance (color, shadow, etc.)
3. Repeat for all variant combinations

**Step 5: Set Default Variant**
1. Right-click main component
2. "Set as default"
3. This is the variant shown in asset library

### Example: Button/Primary Variants

```
Button/Primary (MAIN COMPONENT)
├── State=Default, Size=Small
├── State=Default, Size=Medium ← SET AS DEFAULT
├── State=Default, Size=Large
├── State=Hover, Size=Small
├── State=Hover, Size=Medium
├── State=Hover, Size=Large
├── State=Active, Size=Small
├── ... (continue for all combinations)
└── State=Disabled, Size=Large
```

---

## Testing Checklist

Before finalizing components:

- [ ] All variants render correctly
- [ ] Default variant is clearly marked
- [ ] Property names are consistent across components
- [ ] Text styles are applied (not hard-coded)
- [ ] Colors use shared library colors
- [ ] Spacing uses spacing tokens
- [ ] Shadows use shadow effects
- [ ] All layers are properly named
- [ ] Components are organized in logical structure
- [ ] Auto layout is properly configured
- [ ] Constraints are set for responsive behavior
- [ ] Documentation is complete (see notes)
- [ ] Team members can edit variants without breaking

---

## Quick Reference: Layer Checklist

### Every Button Component Should Have:

- [ ] BG Rectangle with fill and border radius
- [ ] Label Text (centered, white)
- [ ] Icon layer (optional, with spacing)
- [ ] Proper padding via auto-layout
- [ ] All state variants (default, hover, active, disabled)
- [ ] All size variants (small, medium, large)
- [ ] Proper naming convention

### Every Card Component Should Have:

- [ ] BG Rectangle with stroke and shadow
- [ ] Title text (optional via variant)
- [ ] Subtitle text (optional via variant)
- [ ] Content area (flexible height)
- [ ] Proper padding via auto-layout
- [ ] Color variants if metric card (positive, negative, neutral)
- [ ] Hover state with shadow change

### Every Input Component Should Have:

- [ ] BG Rectangle with border
- [ ] Label text (optional via variant)
- [ ] Input text placeholder
- [ ] Error message area (optional via variant)
- [ ] All state variants (default, focused, error, success)
- [ ] Focus shadow/border styling
- [ ] Proper height variants

---

**End of Figma Component Specifications**

Last Updated: 2025-12-07
