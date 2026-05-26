# EventRadar Design System

EventRadar is a mature calendar and activity inbox product. It should feel closer to NetEase Mail, Apple Calendar, Google Calendar, and Outlook Calendar than a demo or crawler dashboard: stable, calm, dense enough for daily use, and easy for ordinary users to understand.

## Principles

- Prioritize the calendar and event inbox. Technical crawling controls are secondary.
- Keep the app shell stable: left navigation, compact top toolbar, central calendar/list, optional right detail/summary rail.
- Keep advanced crawling, proxy, debugging, and raw data controls inside modals, drawers, or collapsed sections.
- Avoid repeating the same event in multiple visible content regions.
- Use compact cards with stable height. Show full details in a modal or drawer.
- Do not use absolute positioning for normal page layout.

## Color

- Background: `#F7F8FA` or `#F8FAFC`.
- Surface: `#FFFFFF`.
- Muted surface: `#F3F6FB`.
- Border: `#E5E8EF`.
- Text primary: `#111827`.
- Text secondary: `#4B5563`.
- Text muted: `#6B7280`.
- Primary color: one low-saturation office blue, currently `#2563EB`.
- Secondary colors: use only for status and priority. Keep them low saturation.
- Avoid large gradients, neon colors, and high-saturation decorative blocks.

## Typography

- Font stack: `-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Segoe UI", sans-serif`.
- Type scale tokens:
  - `--app-font-xs: 11px` for dense metadata and tiny counters.
  - `--app-font-sm: 12px` for badges, button labels, and helper text.
  - `--app-font-base: 13px` for default app body text.
  - `--app-font-md: 14px` for readable form body text.
  - `--app-font-lg: 16px` for section headings.
  - `--app-font-xl: 20px` for page-level titles inside app surfaces.
- Page title: 18-22px inside app surfaces.
- Section title: 14-16px.
- Body text: 13-14px.
- Meta text: 11-12px.
- Letter spacing must stay `0`.
- Avoid viewport-scaled font sizes. Responsive behavior should come from layout, not shrinking text until it becomes unreadable.

## Spacing

Use an 8px spacing system:

- `--app-space-1: 4px`: tiny inline gaps.
- `--app-space-2: 8px`: compact control gaps.
- `--app-space-3: 12px`: card internals and app shell gaps.
- `--app-space-4: 16px`: dense page padding.
- `--app-space-5: 24px`: large page spacing only when truly needed.
- 32px: page-level breathing room.
- Do not use negative margins for app layout.
- Prefer `gap` over ad hoc margins for repeated card, toolbar, and form layouts.

## Cards

- Background: white or subtle translucent white.
- Radius: 8-12px by default. Avoid large rounded cards in productivity surfaces.
- Border: `1px solid #E5E8EF`.
- Shadow: minimal; only modals/drawers use stronger shadows.
- All cards must use `box-sizing: border-box`, `min-width: 0`, and controlled overflow.
- Event cards should have fixed visual rhythm. Clamp title to 2 lines and description/reason to 2-3 lines.

## Buttons

- Primary button: one clear action per surface.
- Secondary button: neutral border and white background.
- Ghost button: quiet navigation or utility action.
- Button scale tokens:
  - `--app-button-sm: 28px` for dense calendar and card actions.
  - `--app-button: 30px` for default desktop toolbar actions.
  - `--app-button-lg: 36px` for forms and primary modal actions.
- Calendar navigation uses compact buttons or icon buttons.
- Buttons must wrap safely on mobile and never overlap.
- Icon-only buttons must have an accessible label.
- Avoid large buttons for secondary actions such as previous, next, refresh, export, or settings.

## Badges

Use unified badges for:

- Priority: `S`, `A`, `B`, `C`.
- Status: `pending`, `confirmed`, `ignored`.
- Favorite and duplicate-source state.

Badges should be pill-shaped, subtle, and compact.

## Layout

- Page container max width: 1440px for app shell surfaces.
- Desktop app shell: left nav 200-220px, main content flexible, right rail 280-320px.
- Use CSS Grid or Flexbox with `min-width: 0`.
- Responsive event card grid:
  - Mobile: 1 column.
  - Tablet: 2 columns.
  - Desktop: 3 columns.
  - Wide screens: maximum 4 columns.
- Avoid masonry layouts.
- Left and right rails may be sticky, but each must have independent scroll and should not force the main content height.
- Month calendar is the default center of gravity. Filters and actions must be compact.
- Breakpoints:
  - `>= 1200px`: full app shell with left nav, central calendar, right rail.
  - `901px - 1199px`: left nav plus main content; right rail moves below the main content.
  - `641px - 900px`: top compact nav, single main column, right rail below in two columns.
  - `<= 640px`: single column, toolbar wraps, right rail one column.
- App surfaces should use height tokens instead of fixed magic numbers where possible.
- If a row cannot fit in a medium-width app window, wrap the toolbar before shrinking text below the type scale.

## Modals And Drawers

- Detail-heavy content belongs in a modal or drawer.
- Modal overlay uses `fixed inset: 0`.
- Panel width should be constrained with `min()`.
- Modal max height: 90vh.
- Long modal content scrolls inside the modal body.
- Z-index scale:
  - `--app-z-nav: 20`
  - `--app-z-sticky: 30`
  - `--app-z-overlay: 1000`
  - `--app-z-popover: 1100`
- Do not add new always-visible forms to the main calendar page. Add an entry point and show the form in a modal or drawer.

## Empty, Loading, Error

- Empty states should explain the next useful action.
- Loading and error states should not collapse the layout.
- Errors should be visible but not visually dominant.

## Event Rendering

- Always deduplicate events before rendering.
- Prefer `event.id` as the stable key.
- If no id exists, use `title + start_time/calendar_time + location + source` as the fallback key.
- Do not render the same event as full cards in multiple visible regions at the same time.
- If duplicates are merged, show duplicate source count in the event detail context or compact badge.

## Current Production Layer

- `static/css/events-app.css` is the production style layer for `static/events.html`.
- `static/js/events-app.js` is the page orchestration layer for `static/events.html`.
- `static/js/state/events-state.js` owns shared state and pure data helpers.
- `static/js/api/events-api.js` owns API helper calls.
- `static/js/render/event-card.js` owns event card and right-rail rendering.
- `static/js/render/calendar-renderer.js` owns calendar, list, and stats rendering.
- `static/js/ui/modals.js` owns modal templates and lazy modal mounting.
- Keep the events page styling in this file so future edits do not create competing CSS layers.
- Avoid reintroducing page-level inline CSS unless the rule is truly critical and cannot live in the stylesheet.
- Prefer `data-action` event binding over inline `onclick`.
- New static controls should be wired in `bindStaticActions()`.
- Dynamic cards may use generated action attributes, but should not reintroduce broad inline script blocks.
- Modals should not be kept as always-on DOM in `events.html`; add a template in `static/js/ui/modals.js` and mount it through `EventRadarModals.ensureModal()`.
- Avoid `!important`. If a rule appears to need it, first fix selector order, stale legacy CSS, or component scoping.
