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
- Page title: 20-24px inside app surfaces.
- Section title: 14-16px.
- Body text: 13-14px.
- Meta text: 11-12px.
- Letter spacing must stay `0`.

## Spacing

Use an 8px spacing system:

- 4px: tiny inline gaps.
- 8px: compact control gaps.
- 12px: card internals and app shell gaps.
- 16px: dense page padding.
- 24px: large page spacing only when truly needed.
- 32px: page-level breathing room.

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
- Normal button height: 32-36px.
- Small button height: 28-32px.
- Calendar navigation uses compact buttons or icon buttons.
- Buttons must wrap safely on mobile and never overlap.

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

## Modals And Drawers

- Detail-heavy content belongs in a modal or drawer.
- Modal overlay uses `fixed inset: 0`.
- Panel width should be constrained with `min()`.
- Modal max height: 90vh.
- Long modal content scrolls inside the modal body.

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
- Keep the events page styling in this file so future edits do not create competing CSS layers.
- Avoid reintroducing page-level inline CSS unless the rule is truly critical and cannot live in the stylesheet.
