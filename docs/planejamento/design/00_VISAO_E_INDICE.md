# Overhaul de Design — Visão geral e índice

> Série de planejamento "Design Massivo" para o UCDM Legends. Cada arquivo cobre uma área do jogo e pode ser executado
> como um update independente (v0.5 → v0.9). Este arquivo define a **visão**, os **princípios** e a **ordem de execução**.

## 1. Por que renovar

O jogo hoje (v0.4.0) já tem botões animados, painéis com degradê, fundo animado e HUD com retratos. Mas o visual ainda é
**genérico**: parece "um bom template" e não "o UCDM". Falta uma identidade que alguém reconheça numa captura de tela de 1 segundo.
O objetivo desta série é transformar o conjunto de menus e telas em uma linguagem visual **única, coesa e dinâmica**.

## 2. Pesquisa e referências (resumo)

| Fonte | O que aproveitamos |
|---|---|
| [Persona 5 — Visual Design of Games](https://mechanicsofmagic.com/?p=7280) e [entrevista PC Gamer](https://www.pcgamer.com/games/rpg/persona-series-director-says-atluss-flashy-menus-are-actually-really-annoying-to-design) | UI como parte da identidade; cada menu com layout próprio (lista, grade, roda); cor forte que se destaca em qualquer fundo; **alerta**: o estilo foi "impossível de ler" no início, legibilidade é lapidada, não presumida |
| [Sakurai — Famitsu vol. 515](https://sourcegaming.info/2016/11/24/the-aims-of-ui-sakurais-famitsu-column-vol-515/) | Organizar informação antes de enfeitar; planejar para localização (textos longos); equilibrar função e charme; cada UI serve a um propósito |
| [Hades — análise de UI responsiva](https://medium.com/@Nat.Rowley/how-hades-creates-a-responsive-underworld-915715a7c2a) | HUD como painel de instrumentos integrado ao mundo; arte, UI e VFX com o mesmo comportamento; telegrafar intenção por animação nítida |
| [Hi-Fi Rush — entrevista Unreal](https://www.unrealengine.com/developer-interviews/hi-fi-rush-was-inspired-by-shaun-of-the-dead-and-futurama) e [MDA](https://mechanicsofmagic.com/?p=25302) | UI sincronizada com a música (pulso), estética de quadrinhos (meio-tom, painéis), baixa taxa de quadros proposital; ensinar pelo que se vê/ouve |
| [Street Fighter 6 — Rolling Stone](https://www.rollingstone.com/culture/rs-gaming/street-fighter-6-what-we-learned-1234746230/) e [crítica Dash Fight](https://dashfight.com/news/street-fighter-6-new-battle-ui-update-leaves-a-lot-to-be-desired-8231) | Direção de arte (grafite/urbano) levada até o HUD e telas de carregamento; **lição**: HUD "bonito" por tema, não só minimalismo neutro; HUDs alternativos/temas |
| [Unity — UI/UX de jogos](https://unity.com/blog/video-game-ui-ux-basics) e [guia de princípios](https://www.strayspark.studio/blog/game-ui-ux-design-principles) | Clareza, feedback, consistência, imersão; "juice" só depois da estrutura estável; destaque de seleção por cor/escala/animação; confirmar/voltar consistentes |
| [Game Accessibility Guidelines](https://gameaccessibilityguidelines.com/basic/), [Xbox XAG 102 contraste](https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/102), [XAG 112](https://devdocs.xbox.com/gaming/accessibility/xbox-accessibility-guidelines/112) | Contraste 4,5:1 (texto) / 3:1 (grande) / 7:1 em modo alto contraste; navegação 100% por teclado/controle; ordem de foco lógica; fonte legível por padrão |

Conclusão que guia tudo: **identidade forte + legibilidade impecável + movimento com propósito**.

## 3. Conceito criativo: "Arena de Lendas — Cartaz de Torneio"

Os personagens são lendas/ícones de uma comunidade (UCDM). A metáfora visual proposta:

- **Cartaz de torneio / revista de luta underground**: papel, tinta, meio-tom (halftone), recortes, carimbos, fita adesiva,
  números grandes de ranking, faixas diagonais.
- **Neon de fliperama** como contraponto: brilho nas bordas, scanlines suaves apenas em momentos de tensão.
- **Fichas e cartas colecionáveis**: cada personagem é uma "carta" com moldura de raridade/estilo.
- **Formas**: cantos chanfrados (corte 45°) em vez de arredondados genéricos; faixas inclinadas em ~-8°; selos circulares.
- **Voz**: curta, ritmada, bem-humorada ("PRÓXIMO DESAFIANTE", "RODADA 3 — VALENDO OURO").

Isso é original, combina com o tema "ucdm", é barato de produzir proceduralmente em pygame (polígonos, ruído, meio-tom gerado)
e é distinto de menus genéricos azuis com degradê.

## 4. Princípios (regras de revisão para qualquer tela nova)

1. **Hierarquia em 3 níveis** por tela: um título/foco, um conjunto de ações, informação de apoio. Se tudo brilha, nada brilha.
2. **Cada tela tem layout próprio** (lista, grade, carrossel, roda, mapa), mas todas compartilham tokens (cores, tipografia, movimento).
3. **Movimento com propósito**: entrada (orienta), foco (confirma), ação (recompensa), saída (fecha o ciclo). Nunca decorativo sem função.
4. **Legibilidade antes de estilo**: texto sobre fundo estampado sempre em painel/placa; testar com contraste ≥ 4,5:1.
5. **Localização**: nenhum texto em tamanho fixo; medir com `font.size`, quebrar linha, reduzir fonte até caber (ver `ui.wrap_text`).
6. **Tudo navegável** por mouse, teclado, gamepad e toque; foco sempre visível; confirmar/voltar iguais em todo menu.
7. **Orçamento de desempenho**: 60 FPS em notebook fraco; superfícies pré-renderizadas e cacheadas; efeitos desligáveis (modo de baixo desempenho).
8. **Tema e dados em JSON**: cores, curvas, durações e textos vêm de arquivos; nada "hardcoded" nas cenas.

## 5. Mapa dos arquivos e ordem de execução

| # | Arquivo | Área | Versão alvo | Depende de |
|---|---|---|---|---|
| 01 | `01_DESIGN_SYSTEM.md` | Tokens, tipografia, cor, componentes base, ícones | 0.5.0 | — |
| 02 | `02_MOVIMENTO_E_TRANSICOES.md` | Linguagem de movimento, transições, ritmo/pulso, som de UI | 0.5.0 | 01 |
| 03 | `03_MENU_PRINCIPAL_E_ABERTURA.md` | Boot, logo, menu principal, notícias | 0.6.0 | 01, 02 |
| 04 | `04_SAVES_PERSONAGENS_E_HUB.md` | Seleção de save, de personagem, hub/campo de treino, treinos | 0.6.0 | 01, 02 |
| 05 | `05_ARENA_BATALHA_E_HUD.md` | Pré-luta (versus), HUD, telegrafia, finalizações | 0.7.0 | 01, 02 |
| 06 | `06_RESULTADOS_PAUSA_E_DIALOGOS.md` | Resultados, pausa, diálogos, toasts, conquistas | 0.7.0 | 01, 02, 05 |
| 07 | `07_OPCOES_AJUDA_E_ESTATISTICAS.md` | Opções, ajuda/tutorial, estatísticas, integridade, créditos | 0.8.0 | 01, 02 |
| 08 | `08_INSTALADOR_E_ATUALIZADOR.md` | Instalador gráfico, tela de atualização, ícone e marca | 0.8.0 | 01 |
| 09 | `09_CONTEUDO_AUDIO_ACESSIBILIDADE_E_ROADMAP.md` | Conteúdo criativo, áudio de UI, acessibilidade, testes, cronograma | 0.9.0 | todos |
| 10 | `10_MINECRAFT_ASSETS.md` | **Integração dos assets de Minecraft** (botões 9-slice, HUD de corações, boss bar, toasts, partículas, itens, panorama), pipeline e licença | transversal (base em 0.5.0) | 01 |

> **Nota:** o UCDM é muito portado para Minecraft, então o arquivo 10 define o tema **"Minecraft"** (pixel-art, ícones de item, HUD de corações)
> usando a pasta `Minecraft Assets` do projeto. Cada plano 01–09 referencia a seção correspondente do 10. A questão de **licença/redistribuição**
> (§11 do arquivo 10) precisa de decisão do dono do projeto antes de publicar uma release com esses assets.

Sugestão de entrega: **0.5 (fundação) → 0.6 (entrada) → 0.7 (combate) → 0.8 (suporte) → 0.9 (polimento e conteúdo) → 1.0**.

## 6. Critérios de sucesso do overhaul

- **Reconhecimento**: uma captura de tela de qualquer menu é identificável como UCDM sem logotipo.
- **Consistência**: auditoria de tokens mostra 0 cores/fonte/duração "soltos" nas cenas.
- **Legibilidade**: 100% dos textos ≥ 4,5:1 (7:1 em alto contraste), em PT e EN, sem corte nem sobreposição em 1280×720 e 1920×720.
- **Fluidez**: 60 FPS estáveis em modo normal; 0 quedas > 33 ms ao abrir/fechar menus.
- **Navegação**: toda tela completável só com teclado, só com mouse, só com gamepad e só com toque.
- **Teste com humanos**: 5 jogadores novos concluem "iniciar jogo → primeira luta" sem ajuda em < 90 s.

## 7. Como executar cada plano

Cada arquivo traz: objetivo, diagnóstico da tela atual, direção de arte, layout (wireframes ASCII), componentes, animações
com durações/curvas, estados, dados/JSON, implementação por arquivo, testes, critérios de aceite e riscos.
Ao implementar: criar branch por arquivo, manter os testes (`python -m unittest`), gerar capturas antes/depois
(scripts de screenshot na pasta de apoio) e atualizar `README.md` + `version.json`.
