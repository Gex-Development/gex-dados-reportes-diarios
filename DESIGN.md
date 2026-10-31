---
name: Relatórios Diários GEX
description: Painel operacional de resultados e conferência de fontes por conta e dia.
colors:
  brand-blue: "#1e6fd9"
  brand-cyan: "#38bdf8"
  accent-ink: "#7fc3ef"
  cat-1: "#1e6fd9"
  cat-2: "#38bdf8"
  cat-3: "#34d399"
  positive-strong: "#4ade80"
  positive-bg: "#123526"
  warning-ink: "#fcd34d"
  warning-bg: "rgba(245, 158, 11, 0.08)"
  warning-border: "rgba(245, 158, 11, 0.35)"
  negative-strong: "#fb7185"
  negative-bg: "#3a1522"
  surface-page: "#000000"
  surface-card: "#131417"
  surface-card-2: "#18191d"
  surface-card-3: "#1b1c20"
  surface-active: "#14202e"
  surface-control: "#202126"
  border-card: "#26272d"
  border-row: "#1b1c20"
  border-strong: "#2e2f36"
  text-primary: "#f4f4f5"
  text-secondary: "#a1a1aa"
  text-muted: "#71717a"
  hero-text: "#ffffff"
  hero-text-muted: "rgba(255, 255, 255, 0.78)"
  glass-bg: "rgba(255, 255, 255, 0.07)"
  glass-border: "rgba(255, 255, 255, 0.16)"
  btn-primary-bg-hover: "#2a7be4"
typography:
  fs-h1:
    fontFamily: "Geist, Geist Variable, system-ui, sans-serif"
    fontSize: "36px"
    fontWeight: 500
    lineHeight: 1.05
    letterSpacing: "-0.03em"
  fs-h2:
    fontFamily: "Geist, Geist Variable, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 600
    letterSpacing: "-0.01em"
  fs-kpi:
    fontFamily: "Geist, Geist Variable, system-ui, sans-serif"
    fontSize: "21px"
    fontWeight: 600
    letterSpacing: "-0.025em"
  fs-body:
    fontFamily: "Geist, Geist Variable, system-ui, sans-serif"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.4
  fs-small:
    fontFamily: "Geist, Geist Variable, system-ui, sans-serif"
    fontSize: "11.5px"
    fontWeight: 400
  fs-caption:
    fontFamily: "Geist, Geist Variable, system-ui, sans-serif"
    fontSize: "10.5px"
    fontWeight: 700
  fs-eyebrow:
    fontFamily: "Geist Mono, Geist Mono Variable, ui-monospace, monospace"
    fontSize: "10px"
    fontWeight: 500
    letterSpacing: "0.1em"
rounded:
  radius-chip: "6px"
  radius-tile: "8px"
  radius-control: "10px"
  radius-tile-xl: "14px"
  radius-tooltip: "14px"
  radius-kpi: "18px"
  radius-card: "22px"
  radius-pill: "999px"
spacing:
  space-1: "3px"
  space-2: "6px"
  space-3: "8px"
  space-4: "10px"
  space-5: "12px"
  space-6: "16px"
  space-7: "20px"
  space-8: "22px"
  space-9: "28px"
  section-gap: "16px"
  page-padding: "18px 28px"
components:
  button-primary:
    backgroundColor: "{colors.brand-blue}"
    textColor: "{colors.hero-text}"
    rounded: "{rounded.radius-control}"
    padding: "9px 16px"
  button-primary-hover:
    backgroundColor: "{colors.btn-primary-bg-hover}"
    textColor: "{colors.hero-text}"
  button-secondary:
    backgroundColor: "{colors.surface-card-2}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.radius-control}"
    padding: "6px 10px"
  card-source:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.radius-kpi}"
    padding: "13px 17px"
  card-section:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.radius-card}"
    padding: "17px 17px 12px"
  chip-divergent:
    backgroundColor: "{colors.warning-bg}"
    textColor: "{colors.warning-ink}"
    rounded: "{rounded.radius-chip}"
    padding: "2px 5px"
---

# Design System: Relatórios Diários GEX

## Overview

**Creative North Star: "Mesa de Conferência GEX"**

Este projeto herda o **GEX Design System** (`gex-design-system`, `tokens.css`) como fonte de verdade. Este documento registra a aplicação observada em `mockups/painel.html`, não redefine a identidade da GEX. A tela coloca o resultado diário ao lado da confiança em cada fonte, em um painel operacional denso, sóbrio e preciso.

A marca aparece no azul, no topo em degradê azul-marinho com brilho ciano e na tipografia Geist, nunca em ornamento. O escuro é o padrão; o claro preserva a mesma semântica com valores próprios em `:root`. Componentes do topo usam vidro somente sobre o degradê. Voz pt-BR, rótulos em Title Case, frases curtas, sem emoji nem exclamação.

**Key Characteristics:**

- Trincas Web | API | Lake deixam a comparação na própria célula da fonte.
- Cor indica identidade da fonte ou estado do dado, sem substituir texto, ícone ou valor.
- Cards de fonte compactos e tabela densa mantêm resultado e divergência juntos.

## Colors

Paleta semântica GEX: azul e ciano da marca; neutros em camadas; âmbar para atenção, verde para igualdade e vermelho somente para problema real ou ausência da fonte.

### Primary

- **Azul GEX** (`--brand-blue`): ação primária e referência de Web por `--cat-1`.
- **Ciano GEX** (`--brand-cyan`): brilho do hero e identidade de API por `--cat-2` no escuro.

### Secondary

- **Verde de Fonte** (`--cat-3`): identidade de Lake; verde de estado (`--positive-strong`) confirma igualdade quando o sinal é positivo, não decora valores.
- **Âmbar de Atenção** (`--warning-bg`, `--warning-border`, `--warning-ink`): divergência e diferença conhecida; delta aparece abaixo do valor na célula da fonte.
- **Vermelho de Ausência** (`--negative-bg`, `--negative-strong`): fonte ausente ou problema real, não divergência comum.

### Neutral

- **Página e Cards** (`--surface-page`, `--surface-card`, `--surface-card-2`, `--surface-card-3`): níveis de fundo e total; `--surface-active` identifica seleção.
- **Texto e Contorno** (`--text-primary`, `--text-secondary`, `--text-muted`, `--border-card`, `--border-row`, `--border-strong`): leitura, hierarquia, controle de tabelas e separação.
- **Texto de Ação** (`--accent-ink`): azul de texto no claro, ciano suave no escuro. `--text-muted` fica restrito a placeholder e rótulo auxiliar, conforme sistema GEX.

**The Fonte Constante Rule.** Web usa `--cat-1`, API usa `--cat-2`, Lake usa `--cat-3` em cards, cabeçalhos e explicações; o tema muda os valores, nunca os papéis.

**The Semântica Antes da Ênfase Rule.** Igualdade é texto secundário com check Lucide; divergência é âmbar com Δ; ausência é chip em `--negative-bg`. Não usar vermelho para discordância ordinária.

## Typography

**Display Font:** Geist (`--font-ui`), com fallback de sistema.
**Body Font:** Geist (`--font-ui`).
**Label/Mono Font:** Geist Mono (`--font-mono`) somente em eyebrow e grupos de colunas em caixa alta.

**Character:** Tipografia contida, tabular para todos os números, com peso suficiente para ler tabela densa sem transformar rótulos em decoração.

### Hierarchy

- **Headline:** `--fs-h1`, peso 500 e espaçamento `--ls-display` no título do topo; reduzido nos pontos de quebra observados.
- **Title:** `--fs-h2`, peso 600 nos títulos de seção; o valor do card de fonte usa a mesma família em peso 600 e tamanho local de 25px no desktop.
- **Body:** `--fs-body` na interface; `--fs-small` em tabela densa, descrição e explicações. Cabeçalhos de tabela usam `--fs-caption` e peso 700.
- **Label:** `--fs-eyebrow`, Geist Mono em caixa alta, peso 500, espaçamento `--ls-eyebrow` e prefixo “• ” apenas acima de títulos de hero e de cards, conforme regra herdada do sistema GEX.

**The Dado Tabular Rule.** `font-variant-numeric: tabular-nums`; dinheiro com símbolo, decimal com vírgula e milhar com ponto. AOV, EPO e Affiliate EPO são médias de contas explicitamente rotuladas “Média das Contas”, nunca somas.

## Layout

Painel central com largura limitada por `--content-max-width` (1560px), margem horizontal `--page-padding` e espaçamento entre seções `--section-gap`. Topo compacto, três cards de fonte lado a lado e tabela com grupos triplos de colunas. A tabela rola dentro do card, com primeira coluna, cabeçalho e rodapé fixos; página não rola horizontalmente. Em até 1020px controles quebram e detalhes passam a uma coluna; em até 690px margens e tipografia encolhem, mantendo os três resumos visíveis. Os valores de espaçamento vêm da escala GEX, não de grade artificial de 4/8px.

**The Base Web Rule.** Totais por fonte consideram apenas as contas da base Web; contas extras de API/Lake aparecem separadamente. Métricas por pedido recebem média simples das contas e rótulo correspondente.

## Elevation & Depth

Profundidade discreta combina camadas tonais, bordas e as sombras GEX `--shadow-card`, `--shadow-kpi` e `--shadow-tooltip`; vidro `--glass-bg` com `--glass-blur` ocorre apenas sobre o topo azul-marinho com `--hero-gradient` e `--hero-glow`. Foco por teclado usa `--focus-ring`; transições curtas usam `--dur-base` e `--ease`, sem quique, e cessam em `prefers-reduced-motion`.

## Shapes

Cards de seção usam `--radius-card`, cards de fonte `--radius-kpi`, controles `--radius-control`, menus `--radius-tooltip`, chips de células `--radius-chip` e filtros sobre o hero `--radius-pill`. Bordas finas definem contorno; cards de fonte têm linha superior mínima na cor da categoria, não moldura de cor inteira.

## Components

### Buttons

- **Primário:** `--brand-blue` com texto branco, `--radius-control`; hover herdado `--btn-primary-bg-hover`, foco `--focus-ring`.
- **Secundário:** fundo `--surface-card-2`, borda `--border-card`, hover `--surface-control`; o exemplo do painel é a ação da seção.
- **Pílula de filtro:** vidro `--glass-bg`, `--glass-border` e `--radius-pill` apenas no hero; hover `--glass-bg-strong`.

### Chips

- **Divergente:** fundo `--warning-bg`, contorno `--warning-border`, Δ sob o valor na célula divergente.
- **Igual:** `--text-secondary` com check Lucide discreto; **ausente:** `--negative-bg` e `--negative-strong`.

### Cards / Containers

- **Fonte:** três resumos Web/API/Lake em `--surface-card` com `--radius-kpi`, borda `--border-card` e `--shadow-kpi`; valor da métrica ativa (a primeira do filtro ou a da ordenação), contas iguais e deltas por fonte, extras apartados.
- **Seção:** `--radius-card`, `--surface-card`, `--border-card`, `--shadow-card`; ícone Lucide em chip `--surface-active` junto do título.

### Inputs / Fields

- **Busca:** caixa `--surface-card-2`, borda `--border-card`, placeholder `--text-muted` e anel `--focus-ring` no contêiner com foco.

### Navigation

- **Barra do topo:** logo GEX, divisor, nome da peça e botão de tema sobre pílula de vidro; a escolha de tema preserva todos os papéis semânticos.

### Tabela de Conferência

- Cada métrica aparece em trinca Web | API | Lake. Célula da fonte guarda seu próprio valor, estado e delta; linha expande para todos os campos. Cabeçalho e total permanecem visíveis durante rolagem; diferença conhecida é explicada em nota, não declarada erro.

## Do's and Don'ts

### Do:

- **Do** reutilizar tokens e regras de `gex-design-system/tokens.css`; esta documentação descreve uso local, não cria paleta paralela.
- **Do** distinguir resultado da fonte de confiança no valor; Web é base e API/Lake se comparam a ele.
- **Do** usar Lucide de traço 2, texto pt-BR em Title Case nos rótulos e valores tabulares brasileiros.
- **Do** manter “• ” em Geist Mono somente no eyebrow GEX acima de títulos de hero e cards, conforme norma herdada.

### Don't:

- **Don't** somar AOV, EPO ou Affiliate EPO nem incluir contas extras no total das contas base.
- **Don't** usar vermelho para uma simples divergência; use âmbar com delta e contexto da fonte.
- **Don't** usar vidro fora do degradê, emoji, exclamação ou efeitos ornamentais para representar marca.
