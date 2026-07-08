# DESIGN.md Template

以下のテンプレートを使って DESIGN.md を生成する。`{...}` はディスカバリーで決定した値で置換する。

---

```markdown
# DESIGN.md

> This file defines the design system for this project.
> AI coding agents MUST reference this file when generating or modifying any UI component.

## Visual Theme & Atmosphere

- **Mood:** {mood_description}
- **Density:** {density — spacious / balanced / dense}
- **Design philosophy:** {philosophy_statement}
- **Reference inspirations:** {reference_sites_or_styles}

## Color Palette

| Role | Value | Usage |
|------|-------|-------|
| Primary | {primary} | Buttons, links, focus rings, active states |
| Primary Hover | {primary_hover} | Button hover, link hover |
| Secondary | {secondary} | Supporting elements, badges, secondary buttons |
| Accent | {accent} | Highlights, call-to-action, notifications |
| Background | {background} | Page background |
| Surface | {surface} | Card backgrounds, elevated elements |
| Surface Alt | {surface_alt} | Alternating rows, subtle section dividers |
| Error | {error} | Error states, destructive action buttons |
| Warning | {warning} | Warning states, caution indicators |
| Success | {success} | Success states, confirmations, positive actions |
| Text Primary | {text_primary} | Main body text, headings |
| Text Secondary | {text_secondary} | Supporting text, labels, placeholders |
| Text Disabled | {text_disabled} | Disabled text, inactive elements |
| Border | {border} | Dividers, input borders, card borders |
| Focus Ring | {focus_ring} | Keyboard focus indicator (accessibility) |

### Dark Mode Overrides (if applicable)

| Role | Value |
|------|-------|
| Background | {dark_background} |
| Surface | {dark_surface} |
| Text Primary | {dark_text_primary} |
| Text Secondary | {dark_text_secondary} |
| Border | {dark_border} |

## Typography

| Level | Font Family | Size | Weight | Line Height | Letter Spacing |
|-------|------------|------|--------|-------------|---------------|
| Display | {display_font} | {display_size}px | {display_weight} | {display_lh} | {display_ls} |
| H1 | {h1_font} | {h1_size}px | {h1_weight} | {h1_lh} | {h1_ls} |
| H2 | {h2_font} | {h2_size}px | {h2_weight} | {h2_lh} | — |
| H3 | {h3_font} | {h3_size}px | {h3_weight} | {h3_lh} | — |
| H4 | {h4_font} | {h4_size}px | {h4_weight} | {h4_lh} | — |
| Body | {body_font} | {body_size}px | {body_weight} | {body_lh} | — |
| Body Small | {body_font} | {body_sm_size}px | {body_weight} | {body_sm_lh} | — |
| Caption | {body_font} | {caption_size}px | {caption_weight} | {caption_lh} | {caption_ls} |
| Code | {code_font} | {code_size}px | {code_weight} | {code_lh} | — |

- **Heading font:** {heading_font_name}, {fallback_stack}
- **Body font:** {body_font_name}, {fallback_stack}
- **Code font:** {code_font_name}, monospace

## Component Stylings

### Buttons

| Variant | Background | Text | Border | Border Radius | Padding |
|---------|-----------|------|--------|---------------|---------|
| Primary | {primary} | {on_primary} | none | {btn_radius}px | {btn_py}px {btn_px}px |
| Secondary | transparent | {primary} | 1px solid {primary} | {btn_radius}px | {btn_py}px {btn_px}px |
| Ghost | transparent | {text_primary} | none | {btn_radius}px | {btn_py}px {btn_px}px |
| Destructive | {error} | white | none | {btn_radius}px | {btn_py}px {btn_px}px |

**States:**
- Hover: {hover_description}
- Focus: {focus_ring} 2px offset ring
- Active: {active_description}
- Disabled: opacity 0.5, cursor not-allowed

### Cards

- Border radius: {card_radius}px
- Background: {surface}
- Border: {card_border}
- Shadow: {card_shadow}
- Padding: {card_padding}px

### Inputs

- Border radius: {input_radius}px
- Border: 1px solid {border}
- Padding: {input_py}px {input_px}px
- Focus: border-color {primary}, box-shadow 0 0 0 2px {focus_ring}
- Error: border-color {error}
- Placeholder: {text_disabled}

### Navigation

- Style: {nav_style}
- Background: {nav_bg}
- Active indicator: {nav_active_style}
- Item padding: {nav_item_padding}

## Layout Principles

- **Base unit:** {base_unit}px
- **Spacing scale:** {spacing_scale}
- **Max content width:** {max_width}px
- **Grid:** {grid_columns} columns, {grid_gap}px gap
- **White space philosophy:** {whitespace_philosophy}
- **Section spacing:** {section_spacing}px between major sections

## Depth & Elevation

| Level | Name | Usage | Shadow |
|-------|------|-------|--------|
| 0 | Flat | Default elements, inline content | none |
| 1 | Raised | Cards, list items | {shadow_1} |
| 2 | Overlay | Dropdowns, popovers, tooltips | {shadow_2} |
| 3 | Modal | Modals, dialogs, drawers | {shadow_3} |
| 4 | Toast | Toast notifications, snackbars | {shadow_4} |

## Do's and Don'ts

### Do
{do_list}

### Don't
{dont_list}

## Responsive Behavior

| Breakpoint | Name | Min Width | Behavior |
|-----------|------|-----------|----------|
| sm | Mobile | {sm_bp}px | {sm_behavior} |
| md | Tablet | {md_bp}px | {md_behavior} |
| lg | Desktop | {lg_bp}px | {lg_behavior} |
| xl | Wide | {xl_bp}px | {xl_behavior} |

- **Touch targets:** minimum {touch_target}px
- **Approach:** {mobile_first_or_desktop_first}
- **Collapse strategy:** {collapse_strategy}

## Agent Prompt Guide

AI コーディングエージェントへの指示:

1. UI コンポーネントを生成・変更する際は、必ずこの DESIGN.md を参照すること
2. Color Palette に定義されていない色を使用しないこと
3. Typography セクションに定義されていないフォントファミリーを導入しないこと
4. Spacing は必ず Spacing scale の値を使用すること
5. Component Stylings に定義されたスタイルを逸脱しないこと
6. 新しいコンポーネントを作る場合は、既存コンポーネントのスタイルパターンに従うこと
7. Dark Mode が定義されている場合は、ライト・ダーク両対応を確認すること
```
