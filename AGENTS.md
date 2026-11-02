# Agents.md

Use `uv add <package>` to install packages. Do not edit `pyproject.toml` dependencies directly.

Use `nvm` - node version manager - to run npm and node commands. Do not install node globally.

Simple solutions over complex ones

## Frontend CSS conventions

All styling tokens are centralized in `webui/src/index.css`. Do not hardcode colors, clip-paths, or other design values in components.

**Colors** — Use theme tokens, never raw hex/rgba:
- Tailwind classes: `bg-primary`, `text-cp-cyan`, `border-primary/20`, `bg-cp-surface3`, etc.
- Inline styles (when needed): `"var(--color-cp-yellow)"`, `"rgb(var(--cp-rgb-yellow) / 0.15)"`
- If a new color is needed, add it to the `@theme` block in `index.css` first. Add an RGB variant in `:root` if alpha support is needed (e.g. `--cp-rgb-foo: R G B`).

**Brightness** — Cyberpunk is bright, not muted:
- Readable text is `text-foreground`, `text-foreground/70` or brighter, or a full accent (`text-primary`, `text-cp-cyan`). Never dimmer.
- No muted grays for text. The `cp-text-muted`, `cp-text-dim`, and `muted-foreground` tokens were removed on purpose — do not reintroduce them. Dark surfaces (`bg-cp-surface*`) are the background, not a text color source.
- Never stack dimming (e.g. `text-foreground/60 opacity-50`). `opacity-*` below 70 is only for interaction states such as `opacity-0 group-hover:opacity-100` reveals.
- Borders must be visible: use the border tokens (`border-border`, `border-cp-border`), not custom faint alphas like `border-white/5` or `border-primary/6`.

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

## Backwards compatibility

There is no need for maintaining backwards compatibility. Prefer proper long-term solutions even if they might introduce breaking changes. The only deployment is [homelab](https://github.com/lordmathis/homelab). Check `mikoshi/plugins` path in the homelab repo if your changes affect any of the plugins and highlight them.

## Comments

Do not write narrative comments. Do not write comments that just repeat what the code does. The only allowed comment is a one-liner that explains a non-trivial detail. No comments is the goal.