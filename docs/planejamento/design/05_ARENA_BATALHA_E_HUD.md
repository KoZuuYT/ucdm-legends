# 05 — Arena: Pré-luta, HUD, Telegrafia e Finalização

**Versão alvo:** 0.7.0 · **Arquivos:** `scenes/arena.py`, `entities/fighter.py`, `systems/particles.py`, `core/feedback.py`

## 1. Objetivo
Fazer a luta **legível em 1 olhar** e **espetacular**: o jogador precisa ler a intenção do inimigo (telegrafia), o estado
dos recursos (HUD) e sentir peso nos impactos. Referências: Hades (intenção telegrafada por animação nítida, HUD como painel
de instrumentos), Street Fighter 6 (identidade temática até o HUD, HUD alternativos), Hi-Fi Rush (pulso e quadrinhos).

## 2. Pré-luta / Versus (já existe base v0.4)
Evoluir para uma sequência estilo **cartaz de luta** (≈ 2,2 s, pulável):
1. Cortina diagonal revela fundo dividido em duas cores (jogador `cool`, inimigo `hot`).
2. Retratos grandes entram em lados opostos com *slide + skew −8°*; nomes em faixas; **estilo e dica** do inimigo ("Blindado: quebre a armadura com parry").
3. "VS" carimba no centro com tremor; barra de **rodada** (3/8) e **recompensa** em ouro aparecem.
4. Mostra **1 dica contextual** (ex.: "Este inimigo usa golpes laranja: aparar ou esquivar").
5. Contagem **3-2-1** em números gigantes que pulsam no BPM; "LUTE!" estoura com partículas.
- Chefe: variante mais longa com frase do chefe e moldura dourada; música muda.

## 3. HUD durante a luta

### Layout (largura dinâmica; elementos nas bordas, centro livre)
```
┌ [retrato] NOME ───── VIDA ██████████░░  ┌──── RODADA 3/8 ────┐ ┌ NOME [retrato] ┐
│  estamina ████░░  [fadiga ▮▮▯]          │      01:12         │ │ VIDA ░░██████  │
│  contra-ataque ★ pronto                 └────────────────────┘ │ ARMADURA ▮▮▮▯  │
└──────────────────────────────────────────                      └ poise ▮▮▯ ──────┘
                        (centro livre: ação)
 [Combo x4 / Estilo]                                  [dica de controle discreta]
```
- **Painéis chanfrados** com retrato, nome e barras; vida troca de cor (mint→accent→hot) e **pulsa** abaixo de 25%.
- **Fantasma de dano** (parte laranja que esvazia depois de 0,4 s) e **brilho de cura/estamina**.
- **Armadura/Poise do inimigo**: segmentos (4–6) que se quebram individualmente com estilhaços; ao zerar, painel treme e carimba "QUEBRADO!".
- **Fadiga**: ícone com contagem; quando ativa, estamina "cansada" (barra tremula e escurece).
- **Contra-ataque pronto**: aura `violet` no retrato + ícone ★ pulsando, com contagem regressiva da janela (1,6 s) em arco.
- **Combo/Estilo**: contador no canto que cresce e "pula" a cada acerto; barra de estilo com níveis (D, C, B, A, S) e carimbo ao subir.
- **HUD alternativos** (como em SF6): "Clássico", "Minimalista" (só barras finas) e "Foco" (informação perto do personagem); escolha em Opções.
- **Dano flutuante**: números com fonte numérica, cor por tipo (normal, crítico dourado maior, bloqueado cinza, contra-ataque violeta, cura mint), movimento em arco, escala pop, limite de números simultâneos.

## 4. Telegrafia e legibilidade de ataques
Princípios: **forma + cor + som + movimento** (nunca só cor — daltonismo).
| Tipo | Cor | Forma | Som | Resposta correta |
|---|---|---|---|---|
| Normal | paper | arco fino no braço | tique | bloquear/esquivar |
| Quebra-guarda | accent/laranja | **triângulo** + aro pulsante | sino agudo | aparar ou esquivar |
| Imbloqueável | hot | **!!** + aro vermelho com raios | alarme curto | esquivar |
| Combo (encadeado) | paper + pontos | pontos indicando nº de golpes | tiques ritmados | ler o ritmo |
- **Anel de timing**: círculo que **encolhe** sobre o inimigo até o instante do impacto; o jogador vê a janela do parry/esquiva perfeita (marca verde final). Opção "Auxílio de timing" mostra/oculta.
- Antecipação do sprite: o inimigo se agacha/ergue (já implementado) com **silhueta realçada** (contorno claro) nos frames críticos.
- **Aviso de direção** para ataques de longe: seta na borda da tela.
- Tempo de leitura mínimo por ataque configurado em `enemies.json` (ex.: `telegraph` ≥ 0,35 s para golpes imbloqueáveis).

## 5. Feedback de impacto (camadas)
Cada evento dispara um **pacote de feedback** configurável em `assets/data/feedback.json`:
- `hit_light`: faísca direcional, hit-stop 30 ms, tremor 2 px, som seco.
- `hit_heavy/crit`: estrela de impacto, hit-stop 70 ms, tremor 5 px, **flash de tela** curto, zoom 3%, som grave.
- `block`: faíscas azuis, escudo brilha, recuo leve.
- `parry`: **anel de choque** + slow-mo 0,35× por 0,25 s + som cristalino + "APARADO!" carimbado.
- `perfect_dodge`: ghost trail + **dessaturação do fundo** por 0,3 s + "ESQUIVA PERFEITA!".
- `armor_break`: estilhaços + hit-stop 90 ms + pop de texto.
- `counter`: linhas de velocidade + moldura violeta nas bordas.
- `ko`: câmera lenta 0,5×, zoom no golpe final, tela em P&B com cor no lutador, "K.O." gigante.
- Respeitar "Reduzir flashes" e "Reduzir tremor" (escalas 0–1 no `feedback`).

## 6. Câmera
- Zoom dinâmico: aproxima em impactos fortes, afasta quando os lutadores se distanciam; limita pela largura do canvas.
- "Câmera de chefe": leve vignette e contorno de energia na fase final.
- Sem rotação (evitar enjoo); tremor com decaimento exponencial.

## 7. Ambiente e plateia
- Plateia reage: pula nos combos, silêncio em perigo, vaia em fuga; usa silhuetas (barato).
- Fundos por **região/rodada** (ginásio, rua, telhado, arena de chefe) com 3 camadas parallax e luzes pulsantes.
- Iluminação "holofote" segue o lutador ativo; sombras elípticas sob os pés.

## 8. Finalização (transição para resultados)
- Último golpe: hit-stop 150 ms + zoom + slow-mo, texto "K.O." ou "DERROTA" em faixa diagonal.
- Vitória: faixa dourada, chuva de confete, retrato do vencedor em destaque, som de fanfarra curta. Derrota: tela escurece, frase do inimigo, opção imediata "Tentar de novo" (1 tecla).

## 9. Implementação
1. Extrair HUD para `scenes/arena_hud.py` (classes `FighterPanel`, `ComboMeter`, `TimingRing`, `DamageNumbers`).
2. `feedback.json` + `core/feedback.py` carregando pacotes; chamar `feedback.play("parry", at=pos)`.
3. Telegrafia: `AttackDef` ganha `warn_shape`, `warn_color`, `read_time`; desenhar anel/triângulo/!! no `Fighter.draw`.
4. Sequência versus em `scenes/versus.py` (timeline com `Seq`).
5. Câmera em `core/camera.py` (zoom/shake com molas).
6. Temas de HUD (`hud_style` em settings) e testes.

## 10. Testes
- Unitários: pacotes de feedback respeitam escalas de acessibilidade; anel de timing coincide com a janela real de parry (±1 frame, teste com `parry_window`).
- Simulação (`sim.py`): HUD não afeta lógica; balanceamento inalterado.
- Capturas: cada tipo de ataque/evento em 1280 e 1920; modo daltônico e alto contraste.
- Perfil: 60 FPS com 3 lutadores + 40 partículas + 8 números de dano.

## 11. Critérios de aceite
- [ ] Jogador novo identifica "o que fazer" ao ver cada ataque colorido/forma em ≤ 1 s (teste com 5 pessoas).
- [ ] Nenhuma informação crítica depende só de cor.
- [ ] Todos os eventos têm som e efeito próprios; efeitos desligáveis.
- [ ] HUD sem sobreposição em ultrawide e com texto 150%.

## 12. Riscos
- **Poluição visual** em combates caóticos → prioridade de feedback (limite de efeitos simultâneos, o mais importante por último).
- **Telegrafia vs. dificuldade**: mais clareza pode facilitar demais → compensar com padrões mais rápidos nas rodadas altas.
