# 03 — Abertura, Menu Principal e Notícias

**Versão alvo:** 0.6.0 · **Arquivos:** `scenes/boot.py`, `scenes/menu.py`, `scenes/news.py`, `systems/backdrop.py`, `systems/ambient.py`

## 1. Objetivo
A primeira impressão: em 5 segundos o jogador entende o tom ("torneio de lendas"), vê movimento vivo, e chega ao botão
**Jogar** sem fricção. Seguindo Sakurai: organizar informação antes de enfeitar; e GAG: iniciar o jogo sem muitos níveis de menu.

## 2. Diagnóstico (v0.4.0)
- Menu: lista vertical de botões com título brilhando e desfile de personagens ao fundo — bom, porém genérico.
- Boot: barra de progresso simples; sem marca/identidade.
- Notícias: texto corrido em painel; sem hierarquia (versão, data, destaques).

## 3. Sequência de abertura (Boot) — 3 a 5 s, pulável
1. **0,0–0,6 s** tela `ink`, ruído de papel; som grave de "impacto".
2. **0,6–1,6 s** o logo **"UCDM LEGENDS"** é *carimbado* (escala 1,6→1, tremor 3 px, poeira, flash curto). Letras em fonte display, com sombra dura.
3. **1,6–3,0 s** faixas diagonais atravessam trazendo silhuetas dos personagens (parallax) enquanto a barra de carregamento aparece como **"fita de pontuação"** com dicas rotativas ("Dica: esquive no último instante").
4. **Fim**: círculo de tinta revela o menu. `Enter/clique` pula; segunda execução do dia usa versão curta (1,2 s).
- Carregamento real (assets, integridade) acontece em segundo plano; a animação nunca atrasa o início se tudo já carregou.
- Rodapé: versão, "verificando atualização…" com ícone giratório → resultado discreto ("Atualizado", "Nova versão v0.x: ver notícias").

## 4. Menu principal — layout

```
┌────────────────────────────────────────────────────────────────────┐
│  [ícone idioma] [ícone som]                          v0.5.0 ● online│
│                                                                    │
│   ╔═ UCDM ══════╗        ░░ desfile de lendas (parallax) ░░         │
│   ║  LEGENDS    ║          silhueta ativa em destaque + nome        │
│   ╚═════════════╝                                                  │
│                                                                    │
│   ▶ CONTINUAR  (Save 2 · Rodada 5 · 1.240 ouro)   ← cartão de save │
│     NOVO JOGO                                                      │
│     SAVES   OPÇÕES   AJUDA   NOTÍCIAS(•)   SAIR                    │
│                                                                    │
│  [Enter] Selecionar  [Esc] Voltar  [F11] Tela cheia    dica rotativa│
└────────────────────────────────────────────────────────────────────┘
```
- **Botão principal contextual**: "CONTINUAR" mostra cartão do último save (retrato, progresso, tempo) em vez de pedir 2 telas.
  Sem save: "JOGAR" (cria um save e vai direto ao hub com tutorial).
- Itens secundários em **fila horizontal compacta** (ícone + rótulo), para reduzir altura e destacar o principal.
- **Notícias**: marcador "•" quando há versão nova/não lida; abre painel lateral, não tela cheia.
- **Fundo vivo**: camadas (céu/arena, plateia, holofotes, partículas) + **desfile** de personagens que passam e param no foco;
  o personagem em foco troca a cada ~6 s com transição de "slide + nome em faixa" e cor de destaque do estilo dele.
- **Pulso**: holofotes e borda do botão seguem o BPM do tema do menu.
- **Easter eggs**: clicar no logo faz o título "vibrar" e solta confete; segredo com sequência de teclas (Konami) altera o tema do menu.

## 5. Estados e interação
- Foco inicial no botão contextual; ←/→ ou ↑/↓ movem foco; mouse hover assume foco; gamepad D-pad/analógico.
- Pressionar "Sair" abre modal de confirmação com opção "Salvar e sair" (se houver progresso não salvo).
- Idioma/Som acessíveis direto do topo (ícones) sem entrar em Opções.
- Ocioso 30 s: entra "modo atração" (câmera passeia, mostra 3 personagens com estatísticas e uma dica) e sai com qualquer entrada.

## 6. Notícias / Novidades (`news.py`)
- Painel com **cartões por versão**: selo de versão, data, 3 destaques com ícone, "ver tudo" expansível.
- Notas vêm de `version.json` (`notes`) + `news.json` opcional (imagens/banners locais ou baixadas com cache).
- Estados: carregando (esqueleto animado), sem internet (mensagem amigável + botão tentar de novo), atualização disponível (botão "Atualizar agora" destacado).
- Marcar como lido remove o "•" do menu; guardar em `settings`.

## 7. Dados
```json
// assets/data/menu.json
{ "tips": ["Esquive no último instante…", "Parry deixa o inimigo atordoado"],
  "idle_seconds": 30,
  "parade": {"interval": 6.0, "shuffle": true},
  "main_buttons": ["continue", "new", "saves", "options", "help", "news", "quit"] }
```

## 8. Implementação (passos)
1. Componentes: `SlantBanner`, `SaveCard`, `IconButton`, `HintBar` (do 01).
2. Reescrever `boot.py` (timeline com `Seq`) e `menu.py` (layout ancorado, botão contextual, fila secundária).
3. `backdrop`: camadas parametrizadas por tema; `ambient`: holofotes/partículas pulsando.
4. `news.py`: cartões, estados de rede, cache de banners.
5. Modo atração e easter eggs (opcional, flag em `menu.json`).
6. Textos em `lang/*.json`; testes de layout em PT/EN (sem corte).

## 9. Testes
- Unitário: ordem de foco, botão contextual com/sem save, marcador de notícias, modo atração (relógio injetável).
- Captura: menu em 1280×720, 1920×720, 4 temas, PT/EN, com e sem save → galeria para revisão.
- Desempenho: menu ≤ 4 ms/frame com desfile ativo.

## 10. Critérios de aceite
- [ ] Do início do processo ao menu interativo ≤ 3 s (pulável em 0 s).
- [ ] "Continuar" leva ao hub em 1 clique/Enter.
- [ ] Menu legível e sem corte em 16:9 e ultrawide; tudo alcançável por teclado/gamepad/toque.
- [ ] Notícias funcionam offline sem erros visíveis.

## 11. Riscos
- Logo/arte final: começar procedural, planejar substituição por arte desenhada.
- Atração/easter eggs são opcionais — cortar primeiro se o prazo apertar.
