# Status de implementação do planejamento de design

Atualizado na v0.9.0. Todos os itens dos 10 planos foram implementados, com as notas de escopo abaixo.

## 01 Design system
- [x] Tema Minecraft e Torneio; tokens de cor do Torneio em `assets/data/theme.json`.
- [x] Fonte bitmap do Minecraft (`core/mcfont.py`, com acentos desenhados à mão), abas/sliders/checkbox com sprites, galeria de componentes (`scenes/gallery.py`, Opções > Sistema ou `--scene gallery`).

## 02 Movimento
- [x] Curvas, mola, sequências e cascata; transição em cortina diagonal; pulso no ritmo; "reduzir movimento".

## 03 Menu e abertura
- [x] Panorama, logo em bloco, splash, Continuar, dicas, notícias; modo atração (45 s parado: luta de demonstração com IA); código Konami.

## 04 Saves, personagens, hub
- [x] Steve fixo, Álbum com raridade/desafios/silhuetas, busca por texto, comparação (tecla de ataque), aparências, estações do hub (cenário por horário), mapa da escada.

## 05 Arena e HUD
- [x] Corações/comida/armadura/chefe, hotbar, partículas do Minecraft, anel de timing, nota S-D, câmera dinâmica, plateia reativa, estilo de HUD (completo/mínimo).

## 06 Resultados, pausa, diálogos
- [x] Nota com carimbo, contador de ouro animado e orbes de XP, árvore de conquistas com ligações, toasts, pausa com resumo.

## 07 Opções, ajuda, estatísticas
- [x] Busca, prévia ao vivo, reverter vídeo em 10 s, tutorial interativo, diagnóstico (copiar informações do sistema), radar e histórico.

## 08 Instalador e atualizador
- [x] Instalador no visual Minecraft (paleta pedra/grama), pausar/retomar download (Range), backup + rollback (`--rollback`, Opções > Sistema), canal beta.

## 09 Conteúdo, áudio, acessibilidade
- [x] Arena Infinita, Desafio do Dia, raridades, conquistas, loja de cosméticos, música dinâmica (versão acelerada na reta final), legendas de efeitos sonoros, modo foto (F12).

## 10 Assets de Minecraft
- [x] Assets em `assets/mc/`, loader 9-slice/tint, manifesto SHA-256 (`tools/make_mc_manifest.py`).
- Nota: o "atlas único" foi dispensado: o loader já guarda cada sprite em cache, sem ganho mensurável.
