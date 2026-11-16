# Status de implementação do planejamento de design

Atualizado na v0.7.0. Legenda: [x] feito, [~] parcial, [ ] não feito.

## 01 Design system
- [x] Tema Minecraft (`core/theme.py`, `assets/data/theme.json`) selecionável nas Opções; botões 9-slice, painéis, texto com sombra.
- [~] Tokens de cor/tipografia em dados: só o seletor de tema e as cores do tema Minecraft; as cores do tema Torneio continuam no código.
- [ ] Fonte bitmap do Minecraft, abas/sliders/checkbox com sprites, galeria de componentes.

## 02 Movimento
- [x] Curvas novas, mola (`Spring`), sequências (`Seq`) e cascata em `systems/tween.py`; logo "carimbado" no boot.
- [x] Transição de cortina diagonal (entrada nas lutas).
- [ ] Pulso no ritmo da música, "reduzir movimento" dedicado.

## 03 Menu e abertura
- [x] Panorama, logo em bloco, frase "splash", botão Continuar com resumo do save, dicas no boot, notícias com ícones.
- [ ] Modo atração, easter eggs.

## 04 Saves, personagens, hub
- [x] Steve fixo, Álbum de Lendas (raridade, desafios, silhuetas), aparências desbloqueáveis, ícone de arma por nível.
- [ ] Busca/filtro por texto no Álbum, comparação, estações do hub, mapa de rodadas visual.

## 05 Arena e HUD
- [x] Corações, comida, armadura e barra de chefe (tema Minecraft), partículas do Minecraft, anel de timing para todos os golpes, nota S-D.
- [x] Hotbar de golpes (ataque, defesa, esquiva, contra-ataque) no tema Minecraft.
- [ ] Estilos alternativos de HUD, câmera com zoom dinâmico, plateia reativa.

## 06 Resultados, pausa, diálogos
- [x] Nota S-D com carimbo, dicas na derrota, conquistas (26) + tela, toasts de avanço, pausa com resumo/reiniciar/ajuda.
- [ ] Contadores animados e orbes de XP voando, árvore de avanços com ligações.

## 07 Opções, ajuda, estatísticas
- [x] Busca nas Opções, auxílio de timing, estatísticas com radar e histórico, créditos com atribuição.
- [ ] Prévia ao vivo das opções, tutorial interativo, diagnóstico, reverter vídeo em 10 s.

## 08 Instalador e atualizador
- [x] Instalador gráfico completo já existente (assistente, atalhos, desinstalar, SHA-256); versão Android (APK) criada.
- [ ] Redesenho visual do instalador no estilo Minecraft, pausar/retomar download, rollback, canais.

## 09 Conteúdo, áudio, acessibilidade
- [x] Arena Infinita, Desafio do Dia (5 modificadores, recompensa dobrada 1x/dia), raridades/desbloqueios, conquistas.
- [ ] Loja de cosméticos, música dinâmica, legendas de efeitos sonoros, modo foto.

## 10 Assets de Minecraft
- [x] Assets em `assets/mc/` (no GitHub), loader com 9-slice/escala inteira/tint, uso em UI, HUD, partículas, ícones.
- [ ] Atlas único e manifesto com SHA-256 dedicado (a verificação de integridade geral já cobre os arquivos).
