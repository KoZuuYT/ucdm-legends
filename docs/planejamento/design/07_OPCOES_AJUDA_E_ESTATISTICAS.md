# 07 — Opções, Ajuda/Tutorial, Estatísticas, Integridade e Créditos

**Versão alvo:** 0.8.0 · **Arquivos:** `scenes/options.py`, `scenes/help.py`, `scenes/stats.py`, `scenes/integrity.py`, `scenes/credits.py` (novo), `core/settings.py`
**Assets Minecraft:** `10_MINECRAFT_ASSETS.md` §5.7 (widgets oficiais, layout de estatísticas, livros na ajuda).

## 1. Objetivo
Telas de suporte **rápidas de usar e agradáveis**: achar uma opção em segundos, entender as regras sem ler um manual, e ver o progresso de forma visual.

## 2. Opções
### Estrutura
Abas em faixa com ícone: **Jogo · Controles · Vídeo · Áudio · Acessibilidade · Idioma** (hoje 5; acessibilidade ganha aba própria).
```
┌ OPÇÕES ───────────────────────────────────────────┐
│ [Jogo][Controles][Vídeo][Áudio][Acessib.][Idioma]  │
│ 🔎 buscar opção…                                   │
│ ┌ lista rolável ──────────────┐ ┌ prévia/descrição ┐│
│ │ Introdução da batalha  [ON] │ │ Mostra a entrada ││
│ │ Auxílio de timing      [ON] │ │ animada e 3-2-1  ││
│ │ Escala do texto   ───●── 120│ │ [mini-prévia ao  ││
│ │ Tema da interface   ◀ Torneio ▶│  vivo]           ││
│ └─────────────────────────────┘ └──────────────────┘│
│ [Restaurar padrões da aba]  [Aplicar]  [Voltar]      │
└─────────────────────────────────────────────────────┘
```
- **Busca** instantânea (nome/descrição/palavras-chave) que atravessa abas.
- **Painel de descrição/prévia** à direita: explica a opção e mostra **prévia ao vivo** (escala de texto, daltonismo, tema, tremor de tela, volume com som de teste).
- **Aplicar/Reverter**: mudanças de vídeo têm contagem de 10 s para confirmar (volta se a tela ficar ilegível).
- **Indicador de alterado** (ponto) e "Restaurar padrões" por aba/por opção.
- **Controles**: tela de remapeamento com **diagrama do teclado/mouse/gamepad**; captura de tecla com animação "pressione…", detecção de **conflito** com troca sugerida; perfis (Padrão, Esquerdista, Gamepad); botões do mouse como ações (já suportado).
- **Tema da interface**: Torneio, Neon, Papel Claro, Daltônico, Alto Contraste, **Minecraft**.
- **Reduzir movimento / flashes / tremor**, **auxílio de timing**, **HUD (Clássico/Minimalista/Foco)**, **tamanho do HUD**, **escala do texto 80–150%**, **legendas de efeitos sonoros** (texto visual para sons importantes).
- Áudio: Mestre, Música, Efeitos, **Interface**; botão "testar".
- Vídeo: tela cheia, limite de FPS, contador de FPS, baixo desempenho, **escala da interface**.

## 3. Ajuda e Tutorial
- **Ajuda** vira um "manual ilustrado" em páginas (índice lateral): Controles (ícones por dispositivo), Combate (parry/esquiva perfeita/contra-ataque/armadura/fadiga com **mini-animações em loop** desenhadas pelo próprio motor), Treinos, Progresso, Dicas.
- Cada página: título em faixa, 1 ideia por tela, exemplo animado, "Tente agora" (leva ao campo de treino com o cenário preparado).
- **Tutorial interativo** (1ª vez, pulável): 5 passos curtos na arena de treino com um boneco — mover, atacar, defender/parry, esquivar no último instante, quebrar armadura. Cada passo mostra o controle com **ícone do dispositivo**, valida a ação e carimba "OK!". Salvar progresso do tutorial.
- **Dicas contextuais** (toasts de tutorial) que aparecem uma única vez quando o jogador encontra algo novo (primeiro golpe laranja, primeira armadura).
- **Glossário** pesquisável (termos: poise, parry, guard break…).

## 4. Estatísticas
- Ficha do lutador: gráfico de **radar** (4 atributos), histórico das últimas 10 lutas (V/D), recordes (maior combo, mais esquivas perfeitas, vitória mais rápida), tempo total.
- Tabela ordenável (cabeçalhos clicáveis ▲▼) por personagem: lutas, vitórias, precisão de parry, ouro ganho.
- Gráficos simples (barras/linha) com cores seguras para daltonismo e rótulos diretos (sem depender de legenda).
- Aba de **conquistas** (06) e **coleção** (personagens usados/total com barra).
- Exportar estatísticas (texto/JSON) para o usuário.

## 5. Integridade e diagnóstico (`integrity.py`)
- Tela de progresso com lista de arquivos (ok/alterado/faltando), barra e resumo; botão "Reparar" (baixa só os arquivos com problema) e "Copiar relatório".
- Linguagem amigável: "3 arquivos precisam ser reparados" em vez de hashes; detalhes recolhíveis.
- **Diagnóstico** (nova sub-tela): versão, SO, FPS médio, driver de vídeo, caminho de saves/logs, botão "Abrir pasta de logs".

## 6. Créditos (novo)
- Rolagem vertical suave com faixas por seção (Design, Código, Arte, Música, Comunidade UCDM, **Agradecimentos**), logotipos/avatares da comunidade, `credits_vignette` de fundo; pausa ao passar o mouse; `Esc` sai.
- Aviso de projeto de fãs e **atribuições de licença** (fontes, assets) lidas de `LICENSES/` e do manifesto.

## 7. Dados e código
- `options.json` declara cada opção (id, aba, tipo, faixa, padrão, palavras-chave, texto de ajuda, prévia) — a tela é **gerada**, não escrita à mão; novas opções = só dados.
- `help.json` (páginas) + animações de ajuda por funções registradas.
- `core/settings.py`: migração de versões, validação, "reverter alteração" em vídeo.

## 8. Testes
Busca encontra por sinônimos (PT/EN); conflito de teclas detectado e resolvido; reversão de vídeo funciona; escala de texto 150% sem corte; tutorial valida cada passo e é pulável; capturas de cada aba em 4 temas.

## 9. Critérios de aceite
- [ ] Achar qualquer opção digitando ≤ 3 letras.
- [ ] Todas as opções com descrição; prévia ao vivo nas visuais.
- [ ] Remapeamento sem estados presos (tecla sempre liberável, `Esc` cancela).
- [ ] Novo jogador conclui o tutorial em < 2 min e entende parry/esquiva (teste com 5 pessoas).

## 10. Riscos
Opção demais confunde → agrupar, padrões bons, "Avançado" recolhido. Tela gerada por dados pode ficar monótona → permitir *widgets* customizados (remapeamento, prévias) por tipo.
