# Agents.md

Use `uv add <package>` to install packages. Do not edit `pyproject.toml` dependencies directly.

Use `nvm` - node version manager - to run npm and node commands. Do not install node globally.

Simple solutions over complex ones

## Frontend CSS conventions

All styling tokens are centralized in `webui/src/index.css`. Do not hardcode colors, clip-paths, or other design values in components.

**Colors** — Use theme tokens, never raw hex/rgba:
- Tailwind classes: `bg-primary`, `text-cp-cyan/20`, `border-primary/6`, `bg-cp-surface3`, etc.
- Inline styles (when needed): `"var(--color-cp-yellow)"`, `"rgb(var(--cp-rgb-yellow) / 0.15)"`
- If a new color is needed, add it to the `@theme` block in `index.css` first. Add an RGB variant in `:root` if alpha support is needed (e.g. `--cp-rgb-foo: R G B`).

**Clip-paths** — Use the CSS utility classes, never inline `clipPath`:
- `cp-cut-{6,8,10,12}` — top-right corner notch
- `cp-cut-br-8` — bottom-right corner notch
- `cp-cut-x-{10,14,16,20}` — opposing top-right + bottom-left notches
- `cp-cut-z-16` — opposing top-left + bottom-right notches
- `cp-diamond`, `cp-tri-bl`, `cp-tri-tr` — decorative shapes
- If a new size/shape is needed, add it as a `.cp-*` class in `index.css`.

**Hover effects** — Use CSS classes, never JS event handlers for style changes:
- `cp-hover-user` — yellow border glow on hover
- `cp-hover-assistant` — red border glow on hover
- `cp-hover-tool` — cyan border brighten on hover

**General rules:**
- Prefer Tailwind utility classes over inline styles.
- If an inline `style` prop is needed (dynamic values, complex backgrounds), use CSS variables — not hardcoded values.
- Do not duplicate values that already exist as theme tokens or utility classes.
