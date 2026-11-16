# 04 — Seleção de Saves, Personagens e Hub de Treino

**Versão alvo:** 0.6.0 · **Arquivos:** `scenes/save_select.py`, `scenes/character_select.py`, `scenes/hub.py`, `scenes/stats.py`, `systems/save.py`

## 1. Objetivo
Tornar a escolha de save e de personagem um momento de **colecionar e se orgulhar** (cartas), e o hub um espaço com
**identidade de academia/ginásio** em que cada treino é legível e recompensador.

## 2. Seleção de save (`save_select.py`)
### Layout: três "fichas" lado a lado (carrossel em telas largas)
```
 ┌ SLOT 1 ───────┐ ┌ SLOT 2 ───────┐ ┌ SLOT 3 ───────┐
 │ [retrato]      │ │ [retrato]      │ │   + NOVO JOGO │
 │ Nome · Nv.     │ │ Nome · Nv.     │ │                │
 │ Rodada 5/8     │ │ Rodada 2/8     │ │                │
 │ Ouro 1.240     │ │ Ouro 300       │ │                │
 │ Jogado 3h12    │ │ Jogado 40min   │ │                │
 │ Última vez: ontem│                 │ │                │
 └────────────────┘ └────────────────┘ └────────────────┘
   [Continuar]  [Renomear]  [Copiar]  [Apagar]  (aparecem no foco)
```
- Cada ficha é uma **carta** (do 01) com moldura do estilo do personagem principal, atributos em mini-barras e **selos** (CHEFE vencido, 100%).
- Foco: a ficha cresce 6%, ganha brilho, demais escurecem; ←/→ troca com mola.
- **Apagar**: modal com texto digitado/segurar-para-confirmar (barra enche 1,2 s) — nada de clique acidental.
- **Copiar/Renomear**: ações secundárias em botões de ícone; "Desfazer apagar" por 10 s (toast com botão), reaproveitando lixeira temporária do `SaveManager`.
- Slot corrompido: ficha com selo `!`, opção de restaurar backup automático.
- Miniatura do save: captura reduzida do hub/arena no momento de salvar (já existe infraestrutura de miniaturas v0.3).

> **Atualização (v0.5.0):** o jogador agora é sempre o **Steve**. `character_select.py` foi substituído por `scenes/collection.py`
> (**Álbum de Lendas** com raridades + **Aparências** do Steve). As lendas são adversários; raridade abre com o avanço na escada da arena.
> As recomendações abaixo (busca, filtros, carta grande, comparação) valem para evoluir esse Álbum.

## 3. Seleção de personagem / Álbum (`collection.py`)
Hoje há 160 personagens; a tela precisa **escalar** sem virar uma lista infinita.

### Layout: grade de retratos + carta grande
```
 ┌──────── grade (rolável, 8×4 visíveis) ───────┐ ┌─ CARTA ──────────┐
 │ □ □ □ □ □ □ □ □                              │ │  [retrato grande] │
 │ □ ▣ □ □ □ □ □ □   ← cursor com moldura       │ │  NOME             │
 │ □ □ □ □ □ □ □ □                              │ │  Estilo · Raridade│
 │ ...                                          │ │  FOR ████░  DEF ███│
 │ [🔎 buscar] [filtro: estilo ▾] [ordem ▾]     │ │  AGI ███░░  FOC ██ │
 └──────────────────────────────────────────────┘ │  Golpe especial    │
                                                  │  "frase de efeito" │
                                                  └────────────────────┘
```
- **Busca por texto**, **filtros** (estilo, raridade, favoritos, bloqueados), **ordenação** (A–Z, força, recém-adicionados).
- **Carta grande** com parallax pelo mouse (inclinação de ±6°), brilho "holográfico" (gradiente que desliza) para raridades altas.
- **Pré-visualização animada**: o personagem faz uma pose idle com os efeitos novos (respiração, contorno), e um botão ▶ "mostrar golpe" toca a animação de ataque.
- **Favoritos** (★) e "Último usado" fixados no topo; atalho de teclado `F` favorita (atenção: conflito com Defender → só nesta tela).
- **Bloqueados**: silhueta + dica de desbloqueio ("Vença o chefe da rodada 4").
- **Comparar**: segurar `Tab` mostra diferenças de atributos contra o personagem atual (setas verde/vermelha).
- **Aleatório**: botão dado 🎲 com animação de roleta em 0,8 s.
- Desempenho: retratos em *atlas* e miniaturas em cache; só desenha itens visíveis (culling já existente); carrega retrato grande sob demanda.

## 4. Hub / Campo de Treino (`hub.py`)
### Conceito: ginásio com estações
- Cena lateral (side-view) onde o jogador anda entre **estações** (Saco de Golpe, Escudo, Esquiva, Mira, Loja de Armas, Arena).
- Cada estação tem **placa luminosa** com ícone, atributo que sobe e nível atual; ao se aproximar, a placa pulsa e mostra o atalho.
- **Painel de status** fixo (lado): nível, atributos com barras animadas, ouro (contador animado), arma e seu nível.
- **Mapa de rodadas** (porta da Arena): trilha de 8 nós com chefe no fim; nós vencidos viram selo dourado; atual pisca.
- Treino concluído: **tela de resultado curta** (ver 06) com estrelas e ganho de atributo "voando" para a barra correspondente.
- **Ciclo dia/noite leve** (opcional): luz do ginásio muda conforme as rodadas avançam, reforçando progresso.
- Personagem sempre virado para o centro/estação (já corrigido na v0.4); NPCs/plateia reagem ao progresso.

### Treinos (mini-jogos) — padrão visual comum
- Introdução de 1,5 s (nome + objetivo + controle), contagem 3-2-1, HUD enxuto (tempo, pontuação, combo), fim com carimbo de nota (S/A/B/C).
- Feedback: cada acerto = partícula + som afinado crescente com o combo; erro = tremor leve.
- Nota afeta ganho de ouro/atributo → incentivo claro, mostrado na tela final ("+2 Força, +35 ouro").

## 5. Estatísticas (`stats.py`)
- Painel de "ficha do lutador": gráficos de radar (4 atributos), histórico de lutas (últimas 10 como pontos V/D), recordes (maior combo, mais esquivas perfeitas, tempo de vitória).
- Conquistas/medalhas em grade com progresso (ver 09).

## 6. Dados e código
- `assets/data/hub.json`: estações (id, posição, ícone, atributo, texto), mapa de rodadas.
- `assets/data/characters.json`: adicionar `rarity`, `style`, `quote`, `unlock` (hoje sem raridade/desbloqueio — decidir regra).
- Novos componentes: `Card`, `CardGrid` (grade virtualizada), `SearchBox` (entrada de texto com cursor piscando, IME seguro), `FilterChips`, `RadarChart`, `HoldButton` (segurar para confirmar).
- `SaveManager`: campos de resumo (`playtime`, `last_played`, `thumbnail`), lixeira temporária, backup automático antes de sobrescrever.

## 7. Testes
- Grade virtualizada: seleção por teclado atravessa linhas/páginas corretamente; busca/filtro/ordem combinados; foco não se perde ao filtrar.
- Save: apagar com confirmação segurada; desfazer; restauração de corrompido.
- Hub: proximidade de estação dispara dica; atalho executa; mapa de rodadas reflete progresso.
- Captura: grade com 160 itens em 1280 e 1920, PT/EN, nomes longos.

## 8. Critérios de aceite
- [ ] Achar um personagem específico (busca) em < 5 s; trocar entre favoritos em 2 ações.
- [ ] Apagar save acidentalmente é impossível; desfazer funciona por 10 s.
- [ ] Hub deixa claro "o que treinar e o que cada treino dá" sem abrir a Ajuda.
- [ ] Seleção de personagem mantém 60 FPS com 160 itens.

## 9. Riscos
- Grade grande + parallax pode custar caro → atlas, cache, parallax só na carta grande.
- Raridade/desbloqueio mexem em progressão → decidir com o `balance.json` e testar com simulação de bots.
