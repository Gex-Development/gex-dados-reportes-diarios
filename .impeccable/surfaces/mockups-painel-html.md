---
version: 1
slug: "mockups-painel-html"
primary_target: "mockups/painel.html"
related_targets: []
---

# Painel de Relatórios Diários

Scope: one Operate surface (static HTML mockup), dark theme default with light complete. Audience and jobs per PRODUCT.md: result of the day (management/finance) and source check (data team).

Task: pick gateway and day, read totals per source, then go account by account through chosen metrics and see, in the cell of each source, whether it matches the web panel.

Proof/content: real reports of BuyGoods 2026-10-28 and PagAmerican 2026-10-29 (web, API, lake) and their diffs.

## Direction contract

THESIS: Every metric is a triplet Web | API | Lake, and divergence sits in the cell of the source that diverges. Refuses the category default of a KPI wall plus one result table that hides where the numbers disagree.

OWN-WORLD: GEX design system dark: navy top gradient with cyan glow, glass pills, #131417 cards, Geist, Geist Mono eyebrows and column-group labels in brand blue, source colours Web #1e6fd9, API #38bdf8, Lake #34d399, amber warning chip with delta for divergence, quiet check for equal.

STORY: The visitor sees the day's Net per source, how many accounts match the panel, then scans the triplet table, filters to divergent accounts, opens one account to see all 11 fields across sources, and reads known differences as known.

FIRST VIEWPORT: Top bar (logo, Relatórios Diários, view switch, theme). Compact hero: eyebrow gateway·day·timezone, H1, filter pills Gateway, Dia, Métricas. Three source cards (Web base, API, Lake) with Net and contas iguais. Below, the Contas por Fonte table fills the rest: Conta + three metric groups of three columns.

FORM: Trincas de Fontes (dealt structure 3 of 3). seed:e82d6aa9ba35084f

SIGNATURE: The triplet column groups with the divergence chip and delta in the exact source cell; clicking a row expands the account into all fields × three sources.
