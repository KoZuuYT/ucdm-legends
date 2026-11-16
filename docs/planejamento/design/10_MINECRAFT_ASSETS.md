# 10 — Integração dos Assets de Minecraft (identidade UCDM × Minecraft)

**Versão alvo:** começa em 0.5.0 (base) e acompanha 0.6–0.9 · **Fonte dos assets:** `D:\usuario alternativo\Documents\Assets Mods Minecraft\Minecraft Assets`
**Arquivos do jogo:** `core/mcassets.py` (novo), `assets/mc/` (cópia filtrada), `assets/data/mc_manifest.json` (novo), `core/ui.py`, `systems/particles.py`

## 1. Por que
O UCDM é muito portado para Minecraft: a comunidade reconhece o visual de blocos, itens, partículas e interface do Minecraft.
Usar esses assets faz o jogo parecer **parte do mesmo universo** (nostalgia + reconhecimento imediato) e entrega arte pronta de
altíssima qualidade para botões, HUD, ícones, partículas e fundos. A identidade "Cartaz de Torneio" (00) continua sendo a **moldura**;
os assets de Minecraft viram o **vocabulário visual** dentro dela.

## 2. Inventário da pasta (3 305 arquivos, 8,7 MB)

| Pasta | Arquivos | O que tem de útil para o jogo |
|---|---|---|
| `gui/sprites/widget` | botão (normal/hover/disabled), slider, alça, checkbox, abas, campo de texto, rolagem, setas de página, cadeado | **Botões 9-slice** (200×20, borda 3) prontos para o `Button`/`Slider`/`Toggle`/`Tabs`/`SearchBox` |
| `gui/sprites/hud` | hotbar, seleção, corações (cheio/meio/piscando/hardcore/envenenado/absorção/congelado/murcho), armadura, comida, experiência, indicador de ataque, mira | **HUD de vida, armadura/poise, estamina (comida), nível/XP**, indicador de ataque/ cooldown, hotbar para golpes |
| `gui/sprites/boss_bar` | 10 cores + versões "notched" 6/10/12/20 | **Barras de vida de inimigo/chefe** (segmentadas = armadura/poise por segmento) |
| `gui/sprites/toast` | advancement, system, tutorial, recipe | **Toasts de conquista/sistema/tutorial** |
| `gui/sprites/popup`, `container`, `statistics`, `icon` | fundo de popup, slots, painéis de estatística, ícones (idioma, acessibilidade, novidades, ping, check) | Diálogos, grade de inventário/personagens, tela de estatísticas, ícones do topo do menu |
| `gui/title` | logo "minecraft", edição, panorama_0–5 + overlay | Referência de **logo em pixel-art 3D** e **panorama giratório** (fundo do menu) |
| `gui/menu_background`, `*_list_background`, separadores | texturas de terra/pedra de menu | Fundo de listas, cabeçalhos e rodapés |
| `font` | ascii, accented (acentos!), nonlatin_european | Fonte bitmap oficial (suporta `ç ã é ê`) para estilo "pixel" |
| `item` (606) | espadas (madeira→netherite), machados, arco/besta, tridente, maça, totem, esmeralda, ouro, diamante, mapa, relógio/bússola animados, livros | **Armas e ícones** (arma do jogador por nível!), moedas (esmeralda/ouro), medalhas, ícones de treino |
| `particle` (230) | `critical_hit`, `sweep_0-7`, `enchanted_hit`, `damage`, `explosion`, `flash`, `spark`, `glint`, `heart`, `angry`, `note`, `soul`, `sonic_boom`, `gust`, `shriek`… | **Partículas de combate** autênticas (golpe crítico, arco de espada, fumaça de explosão) |
| `mob_effect` (40) | ícones de efeitos (força, resistência, lentidão, fraqueza, regeneração…) | **Ícones de status**: fadiga, armadura, contra-ataque, buffs de treino |
| `entity` (608) | mobs, baús, flechas, `experience_orb`, cristal do End, dragão, etc. | Plateia/NPCs/mascotes (mobs como "torcida"), chefes temáticos, orbe de XP como recompensa |
| `block` (1062) | todos os blocos | **Tiles de fundo**: piso do ginásio, paredes, decoração de arena |
| `environment`, `misc` | nuvens, sol, lua, chuva, neve, vinheta, sombra, `enchanted_glint`, `credits_vignette` | Céu da arena, vinheta, sombra sob lutadores, **brilho encantado** em personagens raros |
| `painting` (52), `trims` (60), `map` | quadros, acabamentos de armadura, ícones de mapa | Molduras de cartas, bordas de raridade, **mapa de rodadas** |

## 3. Princípios de uso
1. **Pixel-art autêntica**: escalar **sempre por inteiro (×2, ×3, ×4) com vizinho mais próximo** (`pygame.transform.scale`, nunca `smoothscale`) para manter nitidez. Canvas dinâmico continua suave; os **sprites** é que ficam em escala inteira.
2. **9-slice (`mcmeta`)**: ler `nine_slice` dos `.mcmeta` e desenhar botões/painéis em qualquer tamanho sem distorcer.
3. **Fusão de estilos**: Minecraft entra como **conteúdo** (ícones, botões, barras, partículas); o **cartaz/halftone/faixas inclinadas** continuam como **layout e movimento**. Resultado: UI "pixel-art em faixas de torneio" — único.
4. **Legibilidade**: fonte bitmap só em títulos/valores curtos e opção "Fonte clara" (fonte normal) para quem preferir; contraste conforme 01.
5. **Opcional e trocável**: tema **"Minecraft"** nas Opções (`ui.theme = "minecraft"`) ao lado de Torneio, Neon, Papel, Daltônico e Alto Contraste. Sem os assets, o jogo cai para o tema padrão sem erro.
6. **Sem acoplar ao caminho do usuário**: o jogo **não lê** `D:\...` em tempo de execução; um script copia/filtra os arquivos para `assets/mc/` (ver §4).

## 4. Pipeline de assets (`tools/import_mc_assets.py`)
```
python tools/import_mc_assets.py --src "D:\usuario alternativo\Documents\Assets Mods Minecraft\Minecraft Assets"
```
1. Lê `assets/data/mc_manifest.json` — lista **explícita** dos arquivos usados (id lógico → caminho relativo + escala padrão + 9-slice).
2. Copia somente esses arquivos (~150–250 itens, < 1 MB) para `assets/mc/...` preservando nomes.
3. Empacota ícones pequenos em **atlas** (`assets/mc/atlas_items.png` + JSON de retângulos) para carregar rápido.
4. Valida: arquivo existe, dimensão esperada, `.mcmeta` lido; gera `mc_manifest.lock` com SHA-256 (integra com a verificação de integridade v0.3).
5. Falhas viram aviso (não erro): o tema cai para o padrão.
Runtime: `core/mcassets.py` expõe `mc.sprite("item.diamond_sword", scale=3)`, `mc.nine("widget.button", size)`, `mc.anim("particle.sweep", fps)`, com cache LRU e escalonamento inteiro.

### Manifesto (trecho)
```json
{
  "widget.button":        {"file": "gui/sprites/widget/button.png",             "nine": {"w":200,"h":20,"border":3}},
  "widget.button_hover":  {"file": "gui/sprites/widget/button_highlighted.png", "nine": {"w":200,"h":20,"border":3}},
  "widget.slider_handle": {"file": "gui/sprites/widget/slider_handle.png"},
  "hud.heart_full":       {"file": "gui/sprites/hud/heart/full.png"},
  "hud.heart_blink":      {"file": "gui/sprites/hud/heart/full_blinking.png"},
  "bossbar.red":          {"file": "gui/sprites/boss_bar/red_progress.png"},
  "bossbar.notched_10":   {"file": "gui/sprites/boss_bar/notched_10_progress.png"},
  "item.sword_wood":      {"file": "item/wooden_sword.png"},
  "item.sword_netherite": {"file": "item/netherite_sword.png"},
  "fx.sweep":             {"files": "particle/sweep_{0..7}.png", "fps": 24},
  "fx.crit":              {"file": "particle/critical_hit.png"}
}
```

## 5. Mapeamento por tela (o que entra em cada plano)

### 5.1 Design system (01)
- **Tema "Minecraft"**: paleta extraída das texturas (pedra #6B6B6B/#3C3C3C, madeira, ouro #FCDB05, verde-XP #80FF20, vermelho-coração); botões = `widget.button*` em 9-slice com hover "highlighted" e disabled; slider/checkbox/abas/campo de texto = sprites oficiais; barra de rolagem = `scroller`.
- Cada componente do catálogo ganha **variante "mc"** (mesma API): `Button(style="mc")`.
- Ícones do catálogo: usar **itens** (espada = ataque, escudo/armadura = defesa, bota/pena = esquiva, arco/besta = mira, esmeralda = ouro, relógio = tempo, livro = ajuda, mapa = rodadas, bússola = modo atração) em vez de desenhar com `pygame.draw`.
- Fonte: opção de **fonte bitmap** a partir de `font/ascii.png` + `accented.png` (grade 8×8 → render por glifo com escala inteira).

### 5.2 Movimento (02)
- Partículas de UI: `particle/flash`, `glint`, `spark`, `note` (notas quando música/pulso), `heart` (cura), `glitter`.
- **Brilho encantado** (`misc/enchanted_glint_*`) varrendo cartas e itens raros/em foco (blend aditivo, rolando na diagonal) — o glint do plano vira o glint "de encantamento" que todo jogador de Minecraft reconhece.
- Sons: pacote "mc-like" de UI (clique de botão, XP orb, toast) **somente se** o usuário tiver os `.ogg` (a pasta atual só tem imagens → manter áudio próprio; ver §8).

### 5.3 Abertura e menu (03)
- **Logo**: título "UCDM LEGENDS" com a estética do `gui/title/minecraft.png` (pixel-art em relevo, sombra dura); oscilação sutil e **frase de abertura amarela** ("splash text") girando no canto — tradição do menu do Minecraft, com frases do UCDM.
- **Fundo**: **panorama** com `panorama_0–5` em rotação lenta (ou parallax em camadas feitas de `block/` para o ginásio) + `panorama_overlay`; `environment/clouds` e `sun`/`moon` para ciclo de dia.
- Botões do menu: `widget.button` esticados; **rodapé** com `footer_separator`; ícones do topo (`icon/language`, `accessibility`, `news`).
- **Notícias**: ícone `icon/news` + marcador `icon/unseen_notification`; cartões com `popup/background`.
- Desfile de personagens com **mobs** como figurantes (creeper/vaca/aldeão) atravessando ao fundo, em 2 camadas.

### 5.4 Saves, personagens, hub (04)
- **Fichas de save** = slots do inventário (`container/slot`, `widget/slot_frame`) com retrato; **ícones de mundo** (`world_list`) como miniatura.
- **Grade de personagens** = grade de slots de inventário; cursor = `hotbar_selection`; carta grande com moldura de **quadro** (`painting`) ou acabamento (`trims`) por raridade (cobre, ferro, ouro, diamante, netherita, ametista).
- **Raridade** com cores do jogo: comum (branco), incomum (amarelo), raro (aqua), épico (roxo) + **brilho encantado**.
- **Hub**: estações com blocos reais (bigorna = arma, mesa de encantamento = atributos, mesa de ferreiro, alvo = mira, pilar de treino = golpe, escudo = defesa); **mapa de rodadas** usa `map`/`item/filled_map` e marcadores; plataforma/ piso com tiles de `block/`.
- Pesquisa/filtros: `widget/text_field`, `icon/search`.
- Treinos: ícones de item; nota S–D com **orbes de XP** (`entity/experience_orb`) que voam até a barra.

### 5.5 Arena e HUD (05)
- **Vida = corações** (`hud/heart/*`): vida do jogador em corações (meio-coração = precisão), piscando em dano (`*_blinking`); **hardcore** na rodada do chefe (`hardcore_*`). Alternativa: barra contínua; escolha em "Estilo de HUD".
- **Armadura/poise do inimigo** = ícones `armor_full/half/empty`; **fadiga** = `mob_effect/mining_fatigue` ou `weakness`; **estamina** = drumsticks `food_*` (esvaziam ao esquivar/bloquear; "hunger" quando fadigado).
- **Vida do inimigo/chefe** = `boss_bar` (cor por rodada; chefe = `notched_20`); armadura em segmentos = `notched_6/10`.
- **Indicador de ataque** (`crosshair_attack_indicator_*`, `hotbar_attack_indicator_*`) vira **o medidor de recarga/combo**.
- **Hotbar de golpes**: 3–4 slots (ataque, defesa, esquiva, especial) com ícones de item e recarga; seleção = `hotbar_selection`.
- **Contra-ataque pronto** = `mob_effect/strength` + brilho; **imbloqueável** = `particle/angry` ou ícone de TNT; **quebra-guarda** = machado (`item/*_axe`).
- **Partículas de combate** autênticas: `sweep_0–7` (arco de golpe), `critical_hit` (crítico), `enchanted_hit` (contra-ataque), `damage` (dano), `explosion` (armadura quebrada/KO), `flash` (impacto), `sonic_boom`/`gust` (parry/esquiva perfeita), `shriek`.
- **Sombra** `misc/shadow` sob os lutadores; **vinheta** `misc/vignette` em vida baixa; **plateia** de mobs (`entity/`).
- **Arma do jogador** exibida no HUD e na mão: espada de madeira → pedra → ferro → ouro → diamante → **netherite** conforme nível da arma (já existe progressão de arma no hub).

### 5.6 Resultados, pausa, diálogos (06)
- **Toasts** com `toast/advancement` (conquistas), `toast/system` (avisos), `toast/tutorial` (dicas), com o ícone do item da conquista — idêntico ao "Avanço feito!".
- **Conquistas** no estilo **árvore de avanços** (`advancements/` + `tree`): linhas ligando conquistas, moldura de tarefa/objetivo/desafio, ícone de item. Nomes de conquistas: referências ao Minecraft + UCDM.
- **Resultados**: recompensas como **itens caindo** (esmeraldas/ouro) e **orbes de XP**; nota como "enchanted book" para S.
- **Pausa**: painel de `popup/background`; **diálogos** com botões 9-slice; aviso de perda de progresso estilo "Deseja realmente sair?".

### 5.7 Opções, ajuda, estatísticas (07)
- Opções com **widgets oficiais** (sliders, checkboxes, abas, campo, botões de página); ícone de acessibilidade (`icon/accessibility`) e idioma (`icon/language`) nas abas.
- **Estatísticas** copiam o layout de `statistics/` (ícones `item_used`, `item_crafted`, `block_mined` → "golpes dados", "armaduras quebradas", "esquivas") com cabeçalho `statistics/header` e ordenação ▲▼.
- **Ajuda** com **livros** (`item/written_book`, `knowledge_book`) e páginas viradas (`page_forward/backward`).

### 5.8 Instalador e atualizador (08)
- Instalador (tkinter/pygame) com fundo de terra/pedra (`menu_background`), botões 9-slice, barra de progresso = **barra de XP** (`experience_bar_*`) enchendo; ícone do app com estilo de bloco/item; mensagem "Instalando…" com frase aleatória.

## 6. Conteúdo criativo que isso destrava (fusão UCDM × Minecraft)
- **Mobs como plateia/chefes**: rodadas temáticas por bioma (Planície → Caverna → Nether → End) usando `environment` e `block` de cada bioma; chefes inspirados em mobs (Warden/Dragão) com `entity/*` na plateia e aura própria.
- **Efeitos de status como mecânica visível**: Fadiga = *Mining Fatigue*, Armadura = *Resistance*, Contra-ataque = *Strength*, Parry = *Absorption*, Esquiva perfeita = *Speed* — ícones de `mob_effect` com contagem regressiva sob a barra (cópia do HUD de efeitos).
- **Encantamentos para armas** (loja do hub): lista com `enchanted_book` e brilho; efeitos cosméticos de partícula por encantamento.
- **Cartas colecionáveis** = "quadros" e "faixas de armadura" por raridade.
- **Sistema de XP**: orbes (`experience_orb`) caem dos derrotados e sobem para a barra de nível do HUD.
- **Easter eggs**: frase "splash" amarela, `credits_vignette` nos créditos, `unknown_pack` como ícone padrão de personagem sem retrato.

## 7. Implementação (passos)
1. `tools/import_mc_assets.py` + `mc_manifest.json` (primeiro lote: widgets, heart/armor/food, boss_bar, toast, partículas de combate, ~20 itens).
2. `core/mcassets.py` (cache, escala inteira, 9-slice, animações `mcmeta`, atlas).
3. Tema "Minecraft" no `theme.json` + variante `style="mc"` nos componentes do 01 (botão → slider → toggle → tabs → campo → toast).
4. HUD da arena com corações/armadura/boss bar (05) e partículas `sweep/crit/enchanted_hit` (`systems/particles.py` ganha emissores com sprites).
5. Menu (panorama, logo, splash text), saves/personagens (slots, raridade), hub (blocos/itens).
6. Conquistas em árvore e toasts (06), estatísticas e ajuda (07), instalador (08).
7. Testes e galeria de capturas com o tema "Minecraft" ligado/desligado.

## 8. Áudio
A pasta contém **apenas imagens/JSON** (sem `.ogg`). Opções: (a) continuar com áudio próprio/procedural; (b) se o usuário tiver os sons do jogo, importar via `tools/import_mc_assets.py --audio` pelo mesmo manifesto. **Perguntar antes** de decidir.

## 9. Testes
- `tests/test_mcassets.py`: manifesto válido (todos os arquivos existem), 9-slice produz o tamanho pedido sem erro de borda, escala inteira preserva pixels, animações `mcmeta` avançam, fallback sem assets.
- Captura de **galeria**: botão (3 estados × 5 larguras), HUD de corações (cheio/meio/piscando), boss bar, toast, partículas em sequência.
- Desempenho: atlas único + cache; HUD de corações ≤ 0,5 ms; partículas com sprites ≤ 2 ms para 80 partículas.
- Integridade: `mc_manifest.lock` entra no manifesto de verificação do instalador/atualizador.

## 10. Critérios de aceite
- [ ] Tema "Minecraft" aplica botões, sliders, abas, campo, toasts e HUD oficiais em 100% das telas, sem texto cortado em PT/EN.
- [ ] Pixel-art nítida (escala inteira) em 1280×720 e 1920×720, incluindo janela redimensionada.
- [ ] Jogo funciona **sem** a pasta de origem (apenas com `assets/mc/` empacotado) e **sem** `assets/mc/` (cai no tema padrão).
- [ ] Partículas de combate e corações animam corretamente (`mcmeta`/frames).
- [ ] Tamanho do pacote cresce < 2 MB.

## 11. Decisões e riscos

> **Decisão (16/11/2026):** o dono do projeto informou que o Minecraft permite o uso dos assets sem monetização; portanto os assets
> **ficam no projeto e no GitHub** (`assets/mc/`, cópia integral da pasta de origem). O jogo continua **gratuito, sem monetização**
> e deve manter o aviso de projeto de fãs não afiliado à Mojang/Microsoft. Se o jogo for monetizado um dia, rever essa decisão.
> **Progressão:** o jogador é sempre o **Steve**; as lendas UCDM são adversários com raridade (Comum→Lendário) e aparências do Steve
> desbloqueiam por metas (implementado na v0.5.0: `scenes/collection.py`, `assets/data/rarity.json`, `assets/data/skins.json`).

## 11.1 Riscos originais
- **Licença/marca (importante)**: texturas, logo e sons do Minecraft pertencem à Mojang/Microsoft. Para um projeto de fãs, o uso costuma ser tolerado sob as diretrizes de uso, mas **redistribuir os assets num repositório público/instalador, ou monetizar, pode violar os termos**. Eu não decido isso: recomendo (1) manter o jogo gratuito e com aviso "projeto de fãs, não afiliado à Mojang/Microsoft"; (2) **não usar o logotipo "Minecraft" nem o nome** no título/instalador; (3) decidir se `assets/mc/` vai para o GitHub ou fica fora (nesse caso o jogo usa o tema padrão para quem não tem a pasta) — **validar com a diretriz oficial atual antes de publicar uma release com os assets**.
- **Resolução**: sprites 16×16 ficam pequenos; exigem escala ×3/×4 e podem conflitar com o estilo suave do restante → o tema "Minecraft" deve ser coerente (pixel-art em tudo), não misto.
- **Versão dos assets**: a pasta é de uma versão específica (tem *mace*, *trial*, *breeze*: 1.21+); nomes mudam entre versões → manifesto com caminhos explícitos e lock.
- **Excesso de fan-service** pode reduzir originalidade → manter o cartaz/halftone/faixas como assinatura própria.
