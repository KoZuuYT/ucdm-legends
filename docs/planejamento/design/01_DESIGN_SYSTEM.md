# 01 — Design System "Cartaz de Torneio"

**Versão alvo:** 0.5.0 · **Arquivos principais:** `core/ui.py`, `core/theme.py` (novo), `assets/data/theme.json` (novo), `core/icons.py`

## 1. Objetivo
Criar uma base única (tokens + componentes) para que toda tela herde a identidade, em vez de cada cena escolher cores e tamanhos.
Hoje `ui.py` concentra desenho e estilo; o plano separa **tema (dados)** de **componentes (código)**.

## 2. Diagnóstico (v0.4.0)
- Paleta definida em código e repetida em cenas; mudar o visual exige editar muitos arquivos.
- Tipografia: uma fonte com tamanhos soltos (24, 26, 40…); sem escala.
- Componentes existentes: Button, Menu, bar, panel, backdrop, row. Faltam: abas, cartão, selo, faixa, tooltip, slider estilizado, caixa de seleção, lista rolável, tag/etiqueta, divisor, placa de ranking.
- Sem noção de "elevação", sem texturas, sem moldura de raridade.

## 3. Tokens (arquivo `assets/data/theme.json`)

### 3.1 Cor (paleta base "Tinta & Neon")
| Token | Valor sugerido | Uso |
|---|---|---|
| `ink` | #0E1020 | fundo mais profundo, texto sobre claro |
| `ink_2` | #181B33 | painéis |
| `ink_3` | #242849 | painéis elevados / hover de linha |
| `paper` | #F2E9D8 | "papel" de cartaz, texto sobre escuro |
| `paper_dim` | #B9B2A3 | texto secundário |
| `accent` | #FFC53D | ouro: destaque, foco, recompensa |
| `hot` | #FF3D6E | perigo, ataque, alerta |
| `cool` | #35D0FF | defesa, informação, neon |
| `mint` | #3DFFA8 | sucesso, esquiva perfeita |
| `violet` | #8A5CFF | contra-ataque, raridade épica |
Regras: texto principal = `paper` sobre `ink*` (contraste ≥ 12:1). `accent` sobre `ink` ≥ 9:1. Nunca texto `cool` fino sobre `violet`.
Temas alternativos (opção "Tema da interface"): **Torneio** (padrão), **Neon Noturno** (mais frio), **Papel Claro** (alto contraste claro), **Daltônico** (já existente, reaproveita a paleta segura), **Alto Contraste** (preto/branco/amarelo).

### 3.2 Tipografia
Escala modular 1,25 sobre base 20 px: **12, 15, 20, 25, 31, 39, 49, 61**. Papéis:
- `display` (61/49): títulos de tela e números de round — fonte condensada pesada, caixa alta, leve inclinação (skew −8°).
- `title` (39/31): cabeçalhos de painel.
- `body` (20/25): texto corrido e rótulos de botão.
- `caption` (15/12): dicas, legendas, valores secundários.
- `numeric`: algarismos tabulares (ouro, dano, tempo) para não "dançar".
Fonte: embutir 2 famílias livres (OFL) — uma **display condensada** (ex.: *Bebas Neue*/*Anton*) e uma **texto humanista** com acentos PT completos (ex.: *Barlow*/*Nunito Sans*). Verificar licença e incluir `LICENSES/`. Tudo com fallback para fonte do sistema.
Efeitos de texto prontos (`ui.text(..., style=)`): `outline`, `shadow_hard` (sombra deslocada sem blur, estilo quadrinho), `gradient`, `stamp` (leve rotação + borda), `glow`.

### 3.3 Espaçamento, forma e elevação
- Grade de 8 px (4 px para ajustes finos). Margens de tela: 48 px (16:9) / proporcionais ao canvas largo.
- **Cantos chanfrados**: `cut=10` (botões), `cut=18` (painéis), `cut=28` (cartas). Função `ui.cut_rect(rect, cut, corners)` gera polígono; cache por (w,h,cut).
- Faixa inclinada (`ui.slant_band`) com ângulo `-8°`.
- Elevação: 0 (fundo), 1 (painel), 2 (cartão em foco), 3 (modal). Elevação = sombra dura deslocada + brilho de borda, não blur caro.
- Bordas: 2 px (normal), 3 px (foco), com cor `accent` no foco.
- Textura: **meio-tom (halftone)** e **ruído de papel** gerados 1 vez e reutilizados em painéis (surface 256×256 em tile).

### 3.4 Movimento (tokens)
| Token | Valor |
|---|---|
| `dur_fast` | 0,10 s (hover, press) |
| `dur_base` | 0,22 s (entrada de elemento) |
| `dur_slow` | 0,40 s (troca de painel) |
| `dur_hero` | 0,70 s (tela-cheia) |
| `ease_out` | cúbica-saída (entrada) |
| `ease_in_out` | suavizada (transição) |
| `ease_spring` | mola leve (pop de seleção) |
| `stagger` | 0,04 s entre itens de lista |
Detalhes em `02_MOVIMENTO_E_TRANSICOES.md`.

## 4. Componentes (catálogo)

Cada componente: estados `normal / hover / focus / pressed / disabled / selected`, entrada animada, som, teclado/gamepad/toque.

1. **Botão primário** — placa chanfrada, faixa de brilho diagonal (glint) no hover, "afundar" no press, onda no clique; rótulo com sombra dura. Variantes: primário (accent), secundário (ink_3 + borda), perigo (hot), fantasma (só texto sublinhado).
2. **Botão de ícone** — quadrado chanfrado 48/64 px com ícone vetorial desenhado em código (`core/icons.py` expandido) e dica ao pairar.
3. **Faixa de título (`SlantBanner`)** — título da tela numa faixa inclinada que entra deslizando; subtítulo menor sob ela.
4. **Painel** — chanfrado, textura halftone sutil, borda dupla (clara/escura), canto "cortado" com etiqueta (ex.: "OPÇÕES").
5. **Carta (`Card`)** — proporção 3:4; moldura por raridade/estilo; retrato, nome em placa, estatísticas em barras; inclina em 3D falso (parallax) conforme o mouse.
6. **Aba (`Tabs`)** — abas em faixa; indicador desliza entre abas (lerp), conteúdo troca com deslize curto.
7. **Controle deslizante (`Slider`)** — trilha chanfrada, "alça" com valor flutuante, marcas de passo, clique/arraste/teclas ←/→.
8. **Interruptor (`Toggle`)** e **Seletor (`Chooser`, ◀ valor ▶)** — com mini-animação e texto de estado ("LIGADO"/"DESLIGADO"), nunca só cor.
9. **Lista rolável (`ScrollList`)** — rolagem inercial, barra fina com alça, foco que "segue" o teclado, item selecionado com marcador ▶ animado, máscara de fade nas bordas.
10. **Barra (`Gauge`)** — vida (hot→mint conforme valor), estamina (cool), armadura (paper), poise; "fantasma" que mostra dano recente; segmentos opcionais.
11. **Selo / Etiqueta (`Tag`)** — "NOVO", "CHEFE", "x3", raridades; carimbo com rotação ±6°.
12. **Tooltip** — surge em 0,35 s de hover, ancorado e limitado à tela, com atalho de teclado.
13. **Toast / Notificação** — placa que desliza da lateral com ícone e barra de tempo (já existe base em `feedback`).
14. **Modal** — escurece fundo (`dim_alpha`), painel central com cantos, foco preso (focus trap), `Esc` fecha.
15. **Dica de controle (`HintBar`)** — rodapé com ícones das teclas/botões que mudam conforme o dispositivo ativo (teclado, mouse, gamepad, toque).
16. **Divisor / Régua** — linha tracejada tipo "cortar aqui", usada para organizar seções.
17. **Contador animado** — números que rolam até o valor (ouro, dano), com pulo ao final.
18. **Ícones** — conjunto ~40 ícones vetoriais (espada, escudo, esquiva, mira, moeda, engrenagem, disquete, troféu, relógio, globo, ajuda, jornal, etc.) desenhados com `pygame.draw`, em 3 tamanhos, 1 ou 2 cores; cache por (nome, tamanho, cor).

## 5. Arquitetura de código
```
core/
  theme.py        # carrega theme.json, expõe Theme.color('accent'), Theme.font('title'), Theme.dur('base')
  ui.py           # componentes (separar em core/ui/ pacote se passar de ~1500 linhas)
  ui_draw.py      # primitivas: cut_rect, slant_band, halftone, paper_noise, hard_shadow
  icons.py        # catálogo de ícones
assets/data/theme.json     # tokens + temas alternativos
assets/fonts/              # famílias embutidas + LICENSES
```
- `Theme` aceita troca em runtime (`settings.ui.theme`); componentes leem tokens a cada `draw` (cache invalida ao trocar).
- Todos os componentes recebem `theme` implícito; proibir literais de cor em cenas (teste automático faz `grep` de `(\d+, ?\d+, ?\d+)` em `scenes/`).
- Pré-render: sprite de botão/painel por (tamanho, estado) cacheado em `LRU(256)`; invalidar em mudança de tema ou escala de texto.

## 6. Layout e responsividade (canvas 1280–1920 × 720)
- **Zona segura**: 5% de margem; conteúdo crítico dentro de 1280×720 central; decoração se estende às laterais (já há `Scene.wide`).
- **Ancoragem**: elementos usam âncoras (`left`, `center`, `right`) em vez de coordenadas absolutas.
- **Escala de texto** (acessibilidade 80–150%): componentes medem e crescem; listas viram rolagem quando não cabem.
- **Toque**: alvo mínimo 48×48 px lógicos; espaçamento ≥ 8 px.

## 7. Testes
- `tests/test_theme.py`: todo token existe em todos os temas; contraste calculado (WCAG) ≥ limites para pares texto/fundo declarados.
- `tests/test_ui_components.py`: estados e transições de cada componente (relógio injetável `ui._now`), navegação por teclado/gamepad, foco preso em modal.
- Script `tools/ui_gallery.py`: renderiza **galeria de componentes** em PNG (todos os estados × 3 temas × 2 idiomas) para revisão visual e regressão.

## 8. Critérios de aceite
- [ ] Trocar `theme.json` muda o visual do jogo inteiro sem tocar em código.
- [ ] Galeria cobre 100% dos componentes e estados, sem texto cortado em PT/EN.
- [ ] Contraste validado por teste automático em todos os temas.
- [ ] Nenhuma cena usa cor/fonte literal.
- [ ] Custo de desenho de um menu típico ≤ 3 ms (medido).

## 9. Riscos
- **Fontes**: licença e acentos → usar só OFL e testar `ç ã õ é ê`.
- **Excesso de estilo**: lição de Persona 5 (ilegível no início) → revisar legibilidade com usuários.
- **Custo de CPU** de polígonos chanfrados e texturas → cache agressivo e variante "baixo desempenho" (cantos retos, sem halftone).
