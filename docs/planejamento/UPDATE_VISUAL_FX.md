# UCDM Legends: Update "Visual & Feedback"

Objetivo: fazer o jogo inteiro parecer vivo. Cada golpe, bloqueio, parry, moeda, subida de nível
e troca de tela deve ter resposta visual **e** sonora, com animações dinâmicas, transições suaves,
arte de apresentação (thumbnails, cartões, telas de título) e conteúdo criativo que dê identidade
a cada cenário.

> **Status (v0.2.0, sem release publicada):** implementado: base de feedback (`core/feedback.py`, `systems/tween.py`,
> `feedback.json`), hitstop/câmera lenta no KO, tremor, flash limitado a 3/s, ondas de choque, números de dano com "pop",
> rastro de esquiva, barras de vida fantasma, borda vermelha no golpe imbloqueável, 26 sons e 4 músicas gerados por
> `tools/make_sfx.py`, transições `fade`/`slide`/`iris`, botões animados, toasts, painéis que entram animados, opção *reduzir movimento*.
> **Ficou para depois:** thumbnails (`tools/make_thumbs.py`), fundos com parallax/partículas ambientes por tema, cartões de
> personagem animados, ícones de atributo, ducking além do KO/parry, variação de pitch (hoje há variações de arquivo) e zoom de câmera no KO.
> As decisões da seção 6 foram tomadas assim: sons gerados por código, UI no estilo atual.

Planejamento original:

---

## 0. Diagnóstico do estado atual

Levantado no código em `v0.1.2`:

| Área | Situação | Arquivo principal |
|---|---|---|
| Partículas | Existem (`burst`, textos flutuantes), com pool de 600. Sem trilhas, sem brilho aditivo | `systems/particles.py` |
| Transições | Só fade preto entre cenas (`FADE_TIME`) | `core/scene.py` |
| Câmera / impacto | Não há screen shake, hitstop nem flash de dano | `scenes/arena.py`, `core/engine.py` |
| Fundos | `assets/sprites/backgrounds/` está vazio: o fundo é procedural | `systems/backdrop.py` |
| Áudio | `assets/audio/sfx` e `assets/audio/music` estão **vazios**. Os eventos existem em `game.json`, mas tocam em silêncio | `systems/audio.py`, `assets/data/game.json` |
| Fontes | Não há pasta `assets/fonts/`. Usa a fonte padrão do pygame | `core/ui.py` |
| UI | Botões e painéis simples (`Button`, `Menu`, `panel`) sem animação de hover/foco | `core/ui.py` |
| Personagens | 171 PNGs em `assets/sprites/characters/`, usados em seleção e arena, sem variação de pose | `scenes/character_select.py` |
| Lutadores | Máquina de estados (`fighter.py`) com windup/active/recover, sem squash/stretch nem rastro | `entities/fighter.py` |
| Arte de divulgação | Só `docs/screenshots.png` e o ícone | `docs/`, `installer/art/` |

**Conclusão:** a base de lógica (máquina de estados, pools, eventos, cenas em pilha) já aguenta
o trabalho. O que falta é uma **camada de apresentação** que escute os eventos da luta e do menu
e reaja a eles. Por isso o plano parte de um sistema central de feedback, e não de efeitos
espalhados pelas cenas.

---

## 1. Princípios

1. **Feedback proporcional.** Golpe normal, crítico, parry e golpe imbloqueável têm intensidades
   diferentes. O jogador precisa sentir a diferença sem ler nada.
2. **Acessibilidade primeiro.** Todo efeito de tela (shake, flash, hitstop) tem um controle de
   intensidade em Configurações. Epilepsia: flashes limitados a poucas vezes por segundo, sem
   estroboscópio.
3. **Lógica intacta.** Os efeitos só leem estado. Nada de visual muda dano, timing ou colisão.
   Isso protege o balanceamento e mantém os testes headless válidos.
4. **Custo controlado.** Os efeitos usam pools (`ParticleSystem`), cache de superfícies
   (`AssetManager`) e culling. Meta: 60 FPS estáveis com 144 FPS de teto, no hardware de referência
   (PC modesto, 1280x720), com F3 mostrando o custo.
5. **Sem dependência nova no build.** O build exclui `numpy` e `tkinter`. Qualquer áudio gerado
   por código precisa ser feito com `array`/`wave` da stdlib ou gerado offline por uma ferramenta
   em `tools/`.
6. **Moddável.** Tudo que é visual e sonoro novo passa por `game.json`/`balance.json` e pelo
   sistema de assets, para que mods possam substituir sprites, sons e efeitos.

---

## 2. Arquitetura proposta

### 2.1 Barramento de eventos de feedback

Hoje `core/events.py` existe, mas as cenas chamam partículas e áudio diretamente. Proposta:

```
Fighter / Minigame / Menu  ──emit──▶  FeedbackBus (core/feedback.py)
                                          │
              ┌───────────────┬───────────┼───────────────┬──────────────┐
              ▼               ▼           ▼               ▼              ▼
        CameraFX         ParticleFX    SoundFX         HUDFX         TransitionFX
     (shake, zoom,     (bursts, trails  (sfx com     (barras que    (fades com forma,
      hitstop)          por evento)      variação)     pulsam)        slides, íris)
```

Eventos novos (nomes sugeridos, em `core/feedback.py`):

| Evento | Quando | Payload |
|---|---|---|
| `HIT` | golpe acertou | `pos`, `damage`, `crit`, `attacker`, `target` |
| `BLOCKED` | defesa absorveu | `pos`, `reduction` |
| `PARRY` | bloqueio no instante exato | `pos` |
| `DODGE` | esquiva bem-sucedida | `pos`, `ghost_frames` |
| `HEAVY_WARNING` | aviso vermelho (!!) disparou | `pos`, `duration` |
| `KO` | lutador chegou a 0 HP | `pos`, `who` |
| `COIN` | ouro coletado | `pos`, `amount` |
| `LEVEL_UP` | atributo subiu | `stat`, `pos` |
| `UI_HOVER`, `UI_CLICK`, `UI_CONFIRM`, `UI_BACK` | navegação | `widget` |
| `SCENE_CHANGE` | troca de cena | `kind` (fade, slide, iris) |

Regra: quem emite não sabe quem reage. Isso permite desligar qualquer efeito por configuração.

### 2.2 Novos módulos

| Arquivo | Função |
|---|---|
| `core/feedback.py` | `FeedbackBus` (assinatura de eventos, fila por frame) |
| `systems/camera_fx.py` | shake com decaimento, hitstop (congela só lógica), zoom suave, flash |
| `systems/tween.py` | interpolação com curvas (`ease_out_cubic`, `ease_out_back`, `ease_in_out_sine`), encadeável |
| `systems/trail.py` | rastro de posições (ghost) para dodge, dash e golpe final, em pool |
| `systems/glow.py` | sprite de brilho pré-renderizado + blit aditivo (`BLEND_ADD`) |
| `systems/sfx_bank.py` | variações de som (pitch ±5%, volume ±10%) e limite de voz por evento |
| `systems/transitions.py` | transições de cena: `fade`, `slide`, `iris`, `wipe` |
| `ui/` (novo pacote) | widgets com estado: `AnimatedButton`, `Card`, `Toast`, `Tooltip` |

### 2.3 Estrutura de dados (data-driven)

Novo arquivo `assets/data/feedback.json`:

```json
{
  "intensity": 1.0,
  "flash_max_hz": 3,
  "hitstop": { "normal": 0.03, "crit": 0.06, "parry": 0.09, "ko": 0.14 },
  "shake": { "hit": [3, 0.12], "crit": [7, 0.2], "ko": [12, 0.35] },
  "particles": {
    "hit":   { "count": 14, "color": [255, 220, 140], "speed": 260 },
    "parry": { "count": 28, "color": [120, 220, 255], "speed": 340, "glow": true }
  },
  "sfx_variation": { "pitch": 0.05, "volume": 0.1, "max_voices": 3 }
}
```

Valores de exemplo. Balanceamento final em playtest.

---

## 3. Fases de implementação

Cada fase fecha com testes automáticos (headless) e um teste manual com F3 ligado, anotando
FPS e objetos desenhados.

### Fase 1: Base de feedback (fundação)
- [ ] Criar `core/feedback.py` (`FeedbackBus`), sem efeitos ainda.
- [ ] Criar `systems/tween.py` com curvas e testes unitários (valores de início, fim, monotonia).
- [ ] Criar `systems/camera_fx.py` (shake + hitstop). O hitstop congela `Fighter.update` e o timer
      de minigame, mas **não** a renderização nem o próprio shake.
- [ ] Carregar `assets/data/feedback.json` via `core/config.py` (mesmo mecanismo de mods).
- [ ] Teste: `test_feedback_bus_delivers_in_order`, `test_hitstop_freezes_logic_not_render`.

**Critério de saída:** a arena roda igual à versão atual com `intensity: 0`.

### Fase 2: Impacto na arena (o ganho mais visível)
- [ ] Ligar `HIT`, `BLOCKED`, `PARRY`, `KO` em `scenes/arena.py` e `entities/fighter.py`.
- [ ] Flash branco curto no alvo atingido; cor do flash muda para dourado no crítico e azul no parry.
- [ ] Números de dano com escala (`ease_out_back`) e queda com fade. Crítico maior e com cor própria.
- [ ] "PARRY!" com anel de onda (círculo expansivo, `BLEND_ADD`) e faíscas.
- [ ] Aviso de golpe imbloqueável (!!): pulso de vermelho na borda da tela, respeitando `flash_max_hz`.
- [ ] Rastro do lutador no esquive (`systems/trail.py`, 4 a 6 ghosts, alfa decrescente).
- [ ] KO: câmera dá zoom leve de 1.0 para 1.08 e volta, com hitstop maior.

**Critério de saída:** um parry, um crítico e um KO são distinguíveis só pelo visual, em vídeo gravado.

### Fase 3: Áudio de verdade
Hoje todos os sons estão vazios. Esta fase precisa de decisão de produto (ver seção 6).
- [ ] Definir a origem dos sons: (a) gravação/compra/CC0 ou (b) síntese offline em `tools/make_sfx.py`
      gerando `.ogg`/`.wav` (stdlib `wave` + `array`, sem numpy).
- [ ] Lista mínima: `hit`, `crit`, `block`, `parry`, `miss`, `coin`, `levelup`, `click`, `confirm`,
      `back`, `hover`, `ko`, `whoosh` (dodge), `warning` (!!).
- [ ] Música: `menu`, `hub`, `training`, `arena`, com transição de volume (crossfade de 600 ms já existe em `audio.music`).
- [ ] `systems/sfx_bank.py`: variação de pitch/volume e limite de vozes simultâneas (evita som alto demais em combos).
- [ ] Ducking: a música baixa 20% durante KO e parry.

**Critério de saída:** todo evento da seção 2.1 tem som; faltar arquivo continua silencioso, sem erro.

### Fase 4: Transições e navegação
- [ ] `systems/transitions.py` com `fade` (atual), `slide` (horizontal, para seleção de personagem),
      `iris` (círculo fechando, para KO/derrota) e `wipe`.
- [ ] `scene.py`: `push`, `pop` e `replace` aceitam `kind=` e `duration=`. Padrão continua `fade`.
- [ ] Botões animados: escala 1.0 → 1.05 no foco e no hover, brilho na borda, pequeno "pop" no clique.
- [ ] Painéis entram com slide + fade (`ease_out_cubic`, 180 ms). Sair faz o inverso.
- [ ] Toasts (mensagens curtas empilhadas no canto) para: save automático, novo recorde, atualização disponível.

**Critério de saída:** nenhuma troca de tela corta seco; todas duram entre 150 e 450 ms.

### Fase 5: Personagens, cenários e thumbnails
- [ ] **Cartões de personagem** (seleção): moldura com cor do atributo dominante, sombra, sprite
      com "respiração" (escala 1.0 ↔ 1.02 em 2 s) e leve brilho no foco.
- [ ] **Thumbnails**: gerar miniaturas 256x256 de cada personagem em `assets/sprites/thumbs/`
      (ferramenta `tools/make_thumbs.py`, reaproveitando o pipeline de `import_characters.py`).
      Usadas em seleção, resultados e, no futuro, em menu de conquistas.
- [ ] **Fundos por tema** (`meadow`, `dusk`, `arena`, `night`): camadas com parallax de 2 a 3 planos.
      O suporte a `assets/sprites/backgrounds/<tema>.png` já existe; falta criar as artes ou camadas
      e o parallax em `systems/backdrop.py`.
- [ ] Partículas ambientes por tema (pólen, brasas, poeira, faíscas), no máximo 40 vivas, com pool.
- [ ] Tela de título com logo animado e o personagem escolhido em pose de idle.

**Critério de saída:** o hub e a arena têm pelo menos 3 camadas visíveis e um ambiente animado por tema.

### Fase 6: Polimento de UI e HUD
- [ ] Barras de vida e stamina com "lag" (barra fantasma branca que desce devagar após o dano).
- [ ] Barra de stamina pisca quando abaixo do custo de esquiva.
- [ ] Contador de combo (se houver combo) com escala por nível.
- [ ] Resultados com contagem animada de XP e ouro, e o atributo que subiu brilhando.
- [ ] Ícones de atributo (força, defesa, agilidade, foco) desenhados ou gerados, substituindo cores puras.

### Fase 7: Revisão, performance e acessibilidade
- [ ] Medir com F3: FPS mínimo, objetos desenhados, texturas em cache. Meta: 60 FPS no pior cenário
      (arena com 3 inimigos e todos os efeitos).
- [ ] Teste de estresse headless: 10 000 `burst` e 10 000 `tween` sem alocação por frame
      (contar objetos com `tracemalloc`).
- [ ] Modo "reduzir movimento": desliga shake, zoom e ondas; mantém cores e sons.
- [ ] Revisão de contraste dos textos sobre os novos fundos (mínimo WCAG AA, 4.5:1).
- [ ] Gravar um vídeo curto de cada cena para comparar antes e depois.

---

## 4. Configurações novas (para o update de QoL também)

Adicionar em `settings.json` via o painel de Configurações (o update de QoL cuida da tela):

| Chave | Padrão | Efeito |
|---|---|---|
| `feedback.intensity` | 1.0 | multiplica shake, flash e partículas (0 a 1.5) |
| `feedback.screen_shake` | true | liga/desliga o shake |
| `feedback.flash` | true | liga/desliga flashes de tela |
| `feedback.hitstop` | true | liga/desliga o congelamento de impacto |
| `feedback.reduce_motion` | false | desliga zoom, ondas e parallax |
| `audio.sfx_variation` | true | variação de pitch dos sons |

---

## 5. Testes e validação

**Automáticos (`tests/`):**
- `test_tween_curves`: valores de início e fim, e que curvas `ease_out` não ultrapassam o alvo (exceto `back`).
- `test_hitstop_freezes_logic_not_render`: com hitstop ativo, `Fighter.update` não avança e a cena ainda desenha.
- `test_feedback_intensity_zero_disables_effects`: com `intensity 0`, nenhuma partícula ou shake é criado.
- `test_particle_pool_bounded`: emitir mais que a capacidade não cresce a lista.
- `test_sfx_voice_limit`: no máximo `max_voices` do mesmo evento tocando.
- `test_missing_audio_is_silent`: arquivo ausente não lança exceção.
- Os 12 testes atuais continuam passando.

**Manuais (checklist por fase):**
- F3 ligado, FPS medido em PC de referência.
- Teste com fonte de luz e flash em modo "reduzir movimento" desligado e ligado.
- Jogar uma arena completa sem som, e outra com som, para checar que os efeitos visuais sozinhos já comunicam o parry.

**CI:** o workflow `.github/workflows/release.yml` roda `unittest` no Ubuntu. Testes de áudio
usam o driver `SDL_AUDIODRIVER=dummy`.

---

## 6. Decisões que dependem de você

Preciso de resposta antes da Fase 3 e da Fase 5:

1. **Sons:** prefere (a) sons prontos de uma biblioteca livre/CC0 (mais rápido, qualidade variável)
   ou (b) sons gerados por código (`tools/make_sfx.py`, estilo "chiptune" consistente, sem licença)?
   Para música, há orçamento para compor ou usar IA musical?
2. **Thumbnails:** "thumbnails" interpretado como miniaturas dos personagens nas telas. Também
   quer capas para divulgação (página do GitHub / Release, 1280x640) e miniaturas de vídeo?
3. **Arte de fundo:** pintar os quatro temas à mão, ou criar camadas simples e procedurais
   (formas, silhuetas, gradientes) com parallax?
4. **Estilo:** pixel art (cabe com os sprites atuais) ou visual mais limpo/vetorial para a UI?
   A escolha muda fonte, bordas e efeitos.
5. **Fonte:** há uma fonte da identidade UCDM? Se não, sugiro uma fonte livre de pixel
   (ex.: Press Start 2P, licença OFL) em `assets/fonts/`.

---

## 7. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Efeitos demais deixam o jogo ilegível | alto | `feedback.intensity` e prioridade de efeitos; playtest por fase |
| Queda de FPS com partículas e blends aditivos | médio | pools, pré-render de brilho, F3 como critério de saída |
| Flashes causarem desconforto | alto | limite `flash_max_hz`, modo reduzir movimento |
| Sons gerados soarem amadores | médio | decisão da seção 6; fallback é silêncio, nunca erro |
| Tamanho do pacote crescer (sons, thumbs, fundos) | médio | `.ogg` com qualidade 4–5, thumbs em 256px, imagens de fundo em WebP se o pygame aceitar |
| Mudanças de visual quebrarem telas do update de QoL | médio | os dois planos compartilham a Fase 4 de UI; ver ordem na seção 8 |

---

## 8. Ordem e dependências com o update de Qualidade de Vida

- Fase 1 (base de feedback) deve vir **primeiro**, porque o painel de configurações de feedback
  depende de `feedback.json`.
- As Fases 4 e 6 (UI) mexem nos mesmos arquivos de `core/ui.py` e nas cenas de menu que o update
  de QoL também altera. Fazer um por vez, ou combinar no mesmo branch com revisão.
- A Fase 3 (áudio) não depende de nada e pode rodar em paralelo, se os sons forem gerados por ferramenta.

---

## 9. Versionamento e entrega

- Proposta: **v0.2.0** ("Visual & Feedback"), com as Fases 1 a 4 e 6. Thumbnails e fundos (Fase 5)
  saem na v0.2.1 se o prazo apertar.
- Cada fase vira um commit com mensagem em português. A tag `v0.2.0` só sai depois do checklist
  da seção 5.
- Notas da versão (`version.json → notes`) listam o que o jogador vê, sem jargão técnico.
- Jogadores com saves antigos não perdem nada: o sistema de feedback não altera o formato de save.
