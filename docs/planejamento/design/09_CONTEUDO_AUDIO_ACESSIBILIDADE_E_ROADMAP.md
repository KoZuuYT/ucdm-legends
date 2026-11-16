# 09 — Conteúdo Criativo, Áudio, Acessibilidade, Testes e Roadmap

**Versão alvo:** 0.9.0 → 1.0.0 · **Arquivos:** `assets/data/*.json`, `systems/audio.py`, `core/settings.py`, `tests/`, `tools/`

## 1. Conteúdo criativo (tornar o jogo único)
### 1.1 Mundo e tom
- **Premissa**: um torneio onde as lendas da comunidade UCDM se enfrentam; cada rodada é um **bioma/local** (Ginásio → Rua → Telhado → Caverna → Nether → End → Arena Final), reaproveitando o universo Minecraft da comunidade.
- **Narrador/locutor** de torneio com falas curtas em PT/EN (início de luta, parry, K.O., derrota) em texto (e áudio se houver); humor leve.
- **Frases de efeito** por personagem (carta) e **citações de chefe** no versus.
### 1.2 Personagens (160)
- Campos novos em `characters.json`: `rarity`, `style`, `quote`, `unlock`, `theme_color`, `entrance` (pose de entrada), `victory_pose`.
- **Cartas**: moldura por raridade; versão **brilhante** (shiny) rara; coleção com progresso (X/160) e recompensas por marcos (25/50/100%).
- **Poses e efeitos próprios** (ex.: aura, partículas, rastro colorido) por estilo; compensam sprites estáticos com procedural (squash/stretch já existe).
### 1.3 Progressão e metas
- **Modos**: Torneio (história), **Treino livre**, **Desafios diários** (modificadores: "sem esquiva", "armadura x2", "vida 1"), **Arena Infinita** (ondas) e **Contra-relógio**.
- **Modificadores/Mutadores** desbloqueáveis (cosméticos e de dificuldade com bônus de ouro).
- **Loja de cosméticos** (molduras, trilhas de golpe, temas de HUD) com ouro do jogo — nada que afete o combate.
- **Conquistas** (06) e **galeria** (arte conceitual, retratos, músicas desbloqueáveis).
### 1.4 Miniaturas e capturas
- Gerar miniaturas de saves, cartas e resultados (já há infraestrutura v0.3); **modo foto** (pausa + câmera livre + sem HUD) com exportação de PNG.

## 2. Áudio
- **Música dinâmica** por camadas: base + percussão (entra com a luta) + intensidade (vida baixa/chefe); transições em compasso (BPM em `audio.json`), `Pulse` (02) sincroniza UI.
- **Biblioteca de SFX** organizada: UI (02), combate (golpe leve/pesado/crítico, bloqueio, parry cristalino, esquiva "whoosh", armadura quebrando, K.O.), ambiente (plateia), locutor.
- **Mixer**: Mestre, Música, Efeitos, Interface, Plateia/Ambiente, Voz; ducking da música em modais e falas; compressor leve no master para evitar picos.
- **Mono/estéreo e panning**: efeitos pan conforme posição na tela (sutil).
- **Legendas de efeitos** e **indicadores visuais** de som para acessibilidade (06/07).
- Origem do áudio: própria/procedural ou CC0; **Minecraft**: a pasta fornecida não tem sons — decidir com o usuário (ver `10_MINECRAFT_ASSETS.md` §8).

## 3. Acessibilidade (consolidado)
| Área | Requisito | Referência |
|---|---|---|
| Contraste | ≥ 4,5:1 texto, 3:1 grande, 7:1 no modo alto contraste | Unity / Xbox XAG 102 |
| Navegação | 100% por teclado, mouse, gamepad e toque; ordem de foco lógica; voltar sempre disponível | Xbox XAG 112 |
| Cor | Nada só por cor (forma/ícone/texto); paleta daltônica (3 tipos) | Game Accessibility Guidelines |
| Texto | Tamanho padrão legível, escala 80–150%, fonte alternativa não-pixel | GAG |
| Movimento | Reduzir movimento, flashes (≤ 3 Hz), tremor e zoom; "câmera estável" | GAG / WCAG |
| Dificuldade | Auxílios: janela de parry maior, timing visível, "modo história" (menos dano recebido), **sem punição de acessibilidade** | GAG |
| Som | Legendas de efeitos, indicadores visuais, mixer completo | GAG |
| Entrada | Remapear tudo, segurar vs alternar defesa, sensibilidade de arraste, tempo de clique | GAG |
| Cognitivo | Tutorial pulável e repetível, glossário, dicas consistentes, textos curtos | Sakurai/GAG |
Auditoria: skill/checklist `accessibility-review` antes de cada versão; relatório em `docs/acessibilidade.md`.

## 4. Localização
- Todas as strings via `tr()`; **PT e EN completos**, estrutura pronta para ES/JP (fonte com fallback de glifos).
- Layout **elástico**: textos 40% mais longos não quebram (já medimos com `font.size` e `wrap_text`); teste automático com **pseudo-localização** (acentos + texto alongado) em todas as telas.
- Formatação de números/datas por idioma.

## 5. Qualidade, testes e ferramentas
- **Testes automatizados** (já 92): estender com `test_theme`, `test_ui_components`, `test_mcassets`, `test_results`, `test_achievements`, `test_options_search`.
- **Galeria visual** (`tools/ui_gallery.py`) e **regressão visual**: comparar capturas (tolerância) de todas as telas × temas × idiomas × resoluções (1280×720, 1920×720, 4:3 se aplicável).
- **Perfil de desempenho** (`tools/perf_ui.py`): p95/p99 por tela; limites do plano (≤ 16,7 ms).
- **Simulação de balanceamento** (`sim.py`) a cada mudança de combate.
- **Teste com humanos**: 5–8 pessoas por marco; tarefas: iniciar, achar opção, derrotar rodada 1, usar parry; medir tempo/erros; ajustar.
- **CI**: rodar testes + galeria em headless no GitHub Actions; falha se contraste/overflow quebrar.

## 6. Roadmap e cronograma sugerido

| Versão | Foco | Planos | Esforço (estim.) |
|---|---|---|---|
| 0.5.0 | Fundação: tokens, componentes, movimento, tema Minecraft base, pipeline de assets | 01, 02, 10 (§4) | 2–3 semanas |
| 0.6.0 | Entrada: boot, menu, saves, personagens, hub | 03, 04 | 3 semanas |
| 0.7.0 | Batalha e fechamento: versus, HUD, telegrafia, resultados, pausa, conquistas | 05, 06 | 3–4 semanas |
| 0.8.0 | Suporte: opções, ajuda/tutorial, stats, instalador/atualizador | 07, 08 | 3 semanas |
| 0.9.0 | Conteúdo: modos, desafios, biomas, loja, áudio dinâmico, acessibilidade final | 09 | 3 semanas |
| 1.0.0 | Polimento, testes com humanos, desempenho, documentação, release | todos | 2 semanas |
Regra: **cada versão é publicável** (testes verdes, README e `version.json` atualizados, release automática).

## 7. Métricas de sucesso (1.0)
- Nota ≥ 4/5 de jogadores de teste em "visual" e "clareza".
- Tempo "abrir jogo → primeira luta" ≤ 60 s para novatos.
- Zero relatos de cliques/teclas perdidos; 60 FPS estáveis; 0 textos cortados em PT/EN.
- ≥ 90% das telas com identidade reconhecível em captura anônima.

## 8. Riscos gerais
- **Escopo gigante** → entregar por versões, cortar extras (modo atração, easter eggs, desafios diários) primeiro.
- **Consistência** com tanta variação (temas) → galeria e regressão visual obrigatórias.
- **Licenças** (fontes, áudio, Minecraft) → manifesto de atribuições e revisão antes de cada release.
- **Desempenho** em PCs fracos → modo baixo desempenho testado em cada marco.
