# Dash vs React Look-and-Feel Matrix

## Scope
Visual parity changes applied to React UI to match Dash UI appearance while preserving existing logic.

## Token Map
| Token | Dash Value | Previous React Value | New React Value | File/Class |
|---|---|---|---|---|
| Primary brand | `#8401FF` | `#1d4ed8` | `#8401FF` | `src/styles.css` `:root --brand-primary` |
| Heading text | White on purple | Blue on translucent panel | White on purple header bar | `src/styles.css` `.app-header`, `.header-title` |
| App background | `#f8f9fa` | Gradient blue shell | `#f8f9fa` | `src/styles.css` `body` |
| Card border | `#dddddd` | `rgba(15,23,42,0.08)` | `#dddddd` | `src/styles.css` `--panel-border` |
| Control bg | `#F8F9FA` | Semi-transparent white | `#F8F9FA` | `src/styles.css` `.side-nav-btn` |
| Chat user bubble | `#8401FF` | Translucent blue | Solid `#8401FF` | `src/styles.css` `.chat-bubble-user` |
| Chat assistant bubble | `#e6e6e6` | Translucent green | `#e6e6e6` | `src/styles.css` `.chat-bubble-assistant` |
| Data grid header | `#F5F7FA` + dark text | Blue-tinted header | `#F5F7FA` + `#0F2548` | `src/styles.css` `.MuiDataGrid-columnHeaders` |
| Base font | Gilroy | Inter/Sora | Gilroy | `src/styles.css` `@font-face`, `src/main.tsx` |

## Component-Level Change List
| Area | Change |
|---|---|
| Header | Set brand purple bar, white NIFTY title, removed glass/ambient look |
| Side navigation | Light-gray controls with purple selected state and Dash-like hover |
| Chat shell | Simplified panel, solid assistant/user bubble colors, Dash-like radius/padding |
| Inputs | Dash-like focus ring and control borders |
| Buttons | Dash primary purple with bold text and brightness hover |
| Footer | Dash-like light footer with purple terms/help accents |
| Icons | Migrated high-visibility icons to Font Awesome style |

## Icon Mapping (Font Awesome)
| Previous MUI Icon | New FA Icon | File |
|---|---|---|
| `SearchRounded` | `faMagnifyingGlass` | `src/App.tsx`, `src/components/NifStepSessionPage.tsx` |
| `SchoolRounded` | `faGraduationCap` | `src/App.tsx` |
| `ChecklistRounded` | `faClipboardCheck` | `src/App.tsx` |
| `QuizRounded` / `ContactSupportRounded` | `faCircleQuestion` | `src/App.tsx` |
| `DarkModeRounded` / `LightModeRounded` | `faMoon` / `faSun` | `src/App.tsx` |
| `SmartToyRounded` / `PersonRounded` | `faRobot` / `faUser` | `src/components/ChatModulePage.tsx`, `src/components/NifStepSessionPage.tsx` |
| `SendRounded` | `faPaperPlane` | `src/components/ChatModulePage.tsx`, `src/components/NifStepSessionPage.tsx` |
| Step action icons | `faFloppyDisk`, `faEye`, `faRotate`, `faDownload`, `faArrowsRotate` | `src/components/NifStepSessionPage.tsx` |

## Asset Changes
- Added Gilroy font files to `public/fonts/`:
  - `Gilroy-Regular.ttf`
  - `Gilroy-Bold.ttf`
  - `Gilroy-Heavy.ttf`

## Acceptance Checklist
- [ ] Header looks purple and typography matches Dash brand feel.
- [ ] Side nav default/hover/active states match Dash gray + purple scheme.
- [ ] Chat bubbles match Dash colors (assistant gray, user purple).
- [ ] Font rendering uses Gilroy (with fallback).
- [ ] High-visibility icons render with Font Awesome.
- [ ] Data grid header and density resemble Dash table style.
- [ ] Dark mode still works and keeps same component geometry.
- [ ] No module behavior changes (routing/chat/search/session flow unchanged).

## Screenshot Checklist
1. App header + module navigation (expanded and collapsed nav).
2. NIF Step by Step starter panel and load panel.
3. Chat area with one assistant and one user message.
4. Search NIF table output with header style.
5. Footer + help icon.
6. Dark mode equivalents of all above.
