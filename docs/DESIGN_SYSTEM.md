# Design System & UI Specification

**System Name:** Argvtix Design System  
**Aesthetic Style:** SaaS Engineering-Grade Dark Architecture (Inspired by Linear, Vercel, Datadog & Sentry)  
**Target Viewports:** Mobile ($< 768\text{px}$), Tablet ($768\text{px} - 1024\text{px}$), Desktop ($> 1024\text{px}$)  
**Document Owner:** Senior UI/UX Engineer & Technical Documentation Architect  
**Last Updated:** 2026-10-27  

---

## 1. Visual Identity & Brand Personality

Argvtix's visual identity reflects **precision, enterprise credibility, zero-trust security, and high reliability**.
- **Tone:** Professional, restrained, deterministic, developer-first.
- **Palette Hierarchy:** Deep neutral architectural slate surfaces with high-contrast typography and semantic functional accents (Emerald for safe/verified actions, Amber for warnings/approval holds, Rose for blocks/anomalies, Cyan/Blue for observability feeds).
- **Zero Fluff:** Strictly avoid decorative AI sparkle gradients, generic startup floating blobs, low-contrast text, or sluggish spring physics.

---

## 2. Color Palette & Token Architecture

All colors are declared as CSS custom properties in `ui/src/index.css`:

### 2.1 Surface Layers
```css
--bg-canvas: #090b10;            /* Primary viewport background */
--bg-sidebar: #0c0e14;           /* Persistent navigation sidebar */
--bg-surface: #12151d;           /* Cards, tables, and container blocks */
--bg-surface-elevated: #161b26;  /* Modals, dropdowns, and flyouts */
--bg-surface-hover: #1c2230;     /* Interactive item hover state */
--bg-surface-active: #232a3b;    /* Active click/press state */
```

### 2.2 Borders & Structural Hairlines
```css
--border-subtle: rgba(255, 255, 255, 0.06); /* Dividers and section splits */
--border-default: #1e2433;                    /* Standard card borders */
--border-hover: #2e374d;                      /* Card/input hover border */
--border-active: #404c6b;                     /* Focus and active border */
```

### 2.3 Typography Colors
```css
--text-primary: #f8fafc;   /* Primary headings, titles, and active labels */
--text-secondary: #94a3b8; /* Paragraph copy, subheaders, descriptions */
--text-tertiary: #64748b;  /* Meta timestamps, table headers, labels */
--text-muted: #475569;     /* Disabled text, placeholder indicators */
--text-code: #cbd5e1;      /* Code blocks, JSON keys, trace parameters */
```

### 2.4 Semantic Status Colors
```css
/* Emerald (ALLOW / Success / Verified) */
--emerald: #10b981;
--emerald-subtle: rgba(16, 185, 129, 0.1);
--emerald-border: rgba(16, 185, 129, 0.22);

/* Rose (BLOCK / Error / Critical Anomaly) */
--rose: #ef4444;
--rose-subtle: rgba(239, 68, 68, 0.1);
--rose-border: rgba(239, 68, 68, 0.22);

/* Amber (ASK_HUMAN / Warning / Pending Review) */
--amber: #f59e0b;
--amber-subtle: rgba(245, 158, 11, 0.1);
--amber-border: rgba(245, 158, 11, 0.22);

/* Cyan / Blue (Observability / Info / Active Trace) */
--cyan: #0ea5e9;
--cyan-subtle: rgba(14, 165, 233, 0.1);
--cyan-border: rgba(14, 165, 233, 0.22);
```

---

## 3. Typography & Font Hierarchy

- **UI & Body Font:** `Plus Jakarta Sans`, sans-serif (Weights: 400 regular, 500 medium, 600 semibold, 700 bold).
- **Monospace Font:** `JetBrains Mono`, monospace (Weights: 400, 500). Used for JSON inspection, trace IDs, tool parameters, and SQL queries.
- **Font-Loading Strategy:** Self-contained or preconnected Google Fonts with `display=swap` to eliminate Flash of Invisible Text (FOIT).

### Typographic Scale
- **Display 1 (Landing Hero):** `3.25rem` ($52\text{px}$), line-height `1.15`, weight `800`, letter-spacing `-0.03em`.
- **H1 (Page Titles):** `1.875rem` ($30\text{px}$), line-height `1.25`, weight `700`, letter-spacing `-0.02em`.
- **H2 (Card / Section Headers):** `1.25rem` ($20\text{px}$), line-height `1.35`, weight `600`.
- **H3 (Sub-sections):** `1.0rem` ($16\text{px}$), line-height `1.4`, weight `600`.
- **Body Text:** `0.875rem` ($14\text{px}$), line-height `1.5`, weight `400`.
- **Caption / Meta:** `0.75rem` ($12\text{px}$), line-height `1.4`, weight `500`.

---

## 4. Layout, Spacing & Elevation

### 4.1 Spacing Scale
- `2px` (`0.125rem`): Micro gaps, badges.
- `4px` (`0.25rem`): Icon offsets, tag padding.
- `8px` (`0.5rem`): Form element inner spacing.
- `12px` (`0.75rem`): Compact card padding.
- `16px` (`1.0rem`): Standard container spacing.
- `24px` (`1.5rem`): Section gaps.
- `32px` (`2.0rem`): Page padding, grid column gaps.

### 4.2 Radii Tokens
- `--radius-xs`: `4px` (Tags, code pills)
- `--radius-sm`: `6px` (Buttons, inputs)
- `--radius-md`: `8px` (Standard cards)
- `--radius-lg`: `12px` (Modal windows, panels)
- `--radius-xl`: `16px` (Hero containers)

### 4.3 Elevation & Shadows
- `--shadow-sm`: `0 1px 2px rgba(0, 0, 0, 0.3)`
- `--shadow-md`: `0 4px 12px rgba(0, 0, 0, 0.25)`
- `--shadow-lg`: `0 8px 24px rgba(0, 0, 0, 0.35)`
- `--shadow-popover`: `0 12px 32px rgba(0, 0, 0, 0.5)`

---

## 5. Component Patterns & Conventions

### 5.1 Buttons
- **Primary Action:** Solid background (`--emerald` or `--cyan`), dark text (`#090b10`), bold weight, 6px radius, hover state with brightness increase (`filter: brightness(1.1)`).
- **Secondary / Ghost:** Transparent background, `1px solid var(--border-default)`, `--text-primary` copy, hover with `--bg-surface-hover`.
- **Danger Action:** Solid or bordered with `--rose`, used exclusively for irreversible operations (e.g., rejecting an approval, clearing findings).
- **Disabled State:** Opacity `0.45`, cursor `not-allowed`, zero hover transformations.

### 5.2 Form Inputs
- Background: `--bg-canvas` or `--bg-surface`.
- Border: `1px solid var(--border-default)`.
- Focus State: Visible outline `2px solid var(--cyan)` with `outline-offset: 1px`.
- Validation States: Red border (`--rose`) with explanatory error text below the input field.

### 5.3 Data Tables
- Header: Sticky top, uppercase caption typography (`11px`, weight `600`), background `--bg-sidebar`.
- Rows: Alternating subtle row highlights, `1px solid var(--border-subtle)` dividers, interactive row hover (`--bg-surface-hover`).
- Pagination: Bottom bar with explicit page size selection and disabled arrow states on boundary pages.

### 5.4 Feedback & State Badges
- **Allowed / Success:** Emerald text on `--emerald-subtle` background with `--emerald-border`.
- **Blocked / Critical:** Rose text on `--rose-subtle` background with `--rose-border`.
- **Pending Review:** Amber text on `--amber-subtle` background with `--amber-border`.

### 5.5 Empty & Loading States
- **Loading:** Minimal, crisp CSS spinner or subtle skeleton pulse (`animation: pulse 1.5s ease-in-out infinite`).
- **Empty States:** Clear icon illustration, informative description, and a single primary Call-to-Action (e.g., "Trigger Watchdog Scan" or "Run Benchmark").

---

## 6. Interaction & Accessibility Invariants

1. **Keyboard Accessibility:** All interactive elements (`<button>`, `<a>`, `<input>`, `<select>`) must be navigable via Tab / Shift+Tab and actionable via Enter / Space.
2. **Visible Focus:** Never remove `:focus` outline without providing an explicit `:focus-visible` replacement token.
3. **Reduced Motion:** Honor `prefers-reduced-motion: reduce` by suppressing CSS transitions and animations:
   ```css
   @media (prefers-reduced-motion: reduce) {
     *, *::before, *::after {
       animation-duration: 0.01ms !important;
       transition-duration: 0.01ms !important;
     }
   }
   ```
4. **Contrast Ratios:** Text must satisfy WCAG 2.1 AA minimum contrast ratios ($4.5:1$ for normal body text, $3:1$ for large text and UI components).
