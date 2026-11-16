# 02 — Linguagem de Movimento, Transições e Som de UI

**Versão alvo:** 0.5.0 · **Arquivos:** `systems/tween.py`, `core/scene.py` (transições), `core/ui.py`, `systems/audio.py`, `core/feedback.py`

## 1. Objetivo
Definir **uma gramática de movimento** única: o jogador deve sentir que o menu "tem peso e ritmo", com transições suaves e
feedback sonoro coerente. Referências: UI pulsando com a música (Hi-Fi Rush), menus com identidade própria (Persona), feedback
desproporcional à ação ("juice"), sempre depois de a estrutura estar estável.

## 2. Princípios de movimento
1. **Orientar**: a entrada mostra de onde veio o elemento e para onde vai (pilha de telas = deslocamento espacial consistente).
2. **Confirmar**: toda ação tem resposta em ≤ 100 ms (visual) e ≤ 50 ms (som).
3. **Hierarquia temporal**: o mais importante entra primeiro; o resto escalona (`stagger` 40 ms), total < 600 ms.
4. **Antecipação e sobra** (12 princípios): pequena contração antes de crescer, pequena sobra (overshoot) ao assentar.
5. **Nunca bloquear**: entradas e saídas são cancelam/aceleram se o jogador apertar algo (input buffer durante animação).
6. **Respeitar o usuário**: opção "Reduzir movimento" substitui deslizes/tremores por fades curtos; "Reduzir flashes" já existe.

## 3. Biblioteca de animação (`systems/tween.py`)
Evoluir o tween atual para:
- **Curvas**: `linear, ease_in, ease_out, ease_in_out, back_out (overshoot), elastic_out, bounce_out, spring(damping, stiffness)`.
- **Timeline/Sequência**: `Seq(delay, Tween..., Par(...))` com callbacks; `Stagger(items, step)`.
- **Mola crítica amortecida** (`Spring`) para seguir alvo (cursor, câmera de menu, barras) sem depender de tempo fixo.
- **Valores derivados**: `Pulse(bpm)`, `Shake(amp, decay)`, `Wiggle(freq)`.
- Relógio único (`ui._now`) para testes determinísticos; tweens respeitam pausa e `time_scale` (câmera lenta).

## 4. Catálogo de transições entre telas

| Fluxo | Transição | Duração | Detalhe |
|---|---|---|---|
| Boot → Menu | **Fade da tinta** (círculo de tinta cresce revelando o menu) | 0,7 s | logo "carimba" antes |
| Menu → Hub / Saves | **Deslize lateral + parallax** (fundo move 40%, primeiro plano 100%) | 0,4 s | direção = "avançar" |
| Qualquer → Voltar | Deslize inverso | 0,3 s | mais rápida que entrar |
| Hub → Arena | **Cortina diagonal** (faixas inclinadas fecham e abrem) | 0,6 s | seguida da tela de versus |
| Arena → Resultados | Hit-stop + zoom no último golpe, fade para cor do resultado (ouro/vermelho) | 0,8 s | slow-mo 0,3× por 0,4 s |
| Menu → Opções/Ajuda/Notícias (sobrepostos) | Painel sobe da base + `dim` do fundo + leve desfoque simulado | 0,3 s | |
| Troca de aba | Indicador desliza, conteúdo escorrega 24 px + fade | 0,22 s | direção conforme índice |
| Modal | Escala 0,92→1 com `back_out`, fundo escurece | 0,2 s | |
Todas as transições: interrompíveis, respeitam "Reduzir movimento", usam superfícies pré-capturadas (snapshot) para evitar re-render duplo.

**Desfoque barato**: snapshot reduzido a 1/4 + `smoothscale` de volta (2 passes) — custo baixo e visual de vidro fosco para modais.

## 5. Microinterações (por tipo de elemento)
- **Hover**: elemento sobe 2 px, borda vira `accent`, glint diagonal passa 1× (a cada 3 s se continuar em foco).
- **Foco por teclado/gamepad**: marcador ▶ desliza até o item (mola), item cresce 4%.
- **Press**: afunda 3 px + escurece; **release**: sobra de 6% e partículas curtas.
- **Seleção confirmada**: onda circular do ponto do clique (já existe `ripple`) + pop do ícone.
- **Valores numéricos**: contador rola; ao subir fica `mint` 0,4 s, ao descer `hot`.
- **Sliders**: valor flutua acima da alça e some 0,6 s após soltar; tique sonoro a cada passo.
- **Erro/Indisponível**: balançar horizontal (±6 px, 3 ciclos, 0,25 s) + som seco + dica do motivo.
- **Listas**: ao entrar, itens fazem `stagger` vindo da esquerda inclinados −8°; ao rolar, inércia + fade de borda.
- **Barras**: enchem com mola; dano mostra "fantasma" laranja que esvazia depois de 0,4 s.
- **Títulos**: "carimbo" — começam grandes e transparentes, batem na tela com tremor de 2 px e partículas de poeira.

## 6. Ritmo e pulso (assinatura do jogo)
- `Pulse` global derivado do BPM da música atual (campo `bpm` em `assets/data/audio.json` por faixa).
- Elementos "vivos" pulsam sutilmente no tempo: brilho do logo, borda do botão em foco, luzes do fundo, silhuetas da plateia.
- Na arena o pulso acelera com a tensão (vida baixa, chefe em fase final).
- Fallback sem música: pulso fixo 90 BPM com amplitude mínima; desligável.

## 7. Som de UI (acompanha movimento)
Biblioteca de ~30 efeitos curtos (gerados proceduralmente ou de pacote CC0), agrupados:
- `ui_hover` (tique suave, pitch varia ±3% para não cansar), `ui_focus`, `ui_confirm` (duas notas ascendentes), `ui_back` (descendente),
  `ui_error`, `ui_toggle_on/off`, `ui_slider_tick`, `ui_tab`, `ui_modal_open/close`, `ui_stamp` (título), `ui_swipe` (transição),
  `ui_coin_count` (contador), `ui_unlock` (arpejo), `ui_toast`.
- **Regras**: máx. 3 vozes de UI simultâneas; debounce de 40 ms em hover; ducking leve da música (−3 dB) em modais; canal separado "Interface" no mixer das Opções.
- Cada som tem o equivalente visual (acessibilidade): quem joga sem áudio não perde informação.

## 8. Orçamento e desempenho
- Meta: animações de UI custam ≤ 1,5 ms/frame. Evitar alocar superfícies por frame (reutilizar buffers).
- Modo baixo desempenho: sem glint, sem partículas de UI, transições viram fade 0,15 s.
- Medir com `tools/perf_ui.py` (percorre todas as telas e registra p95 do tempo de frame).

## 9. Implementação (passos)
1. Estender `tween.py` (curvas, Seq, Spring) + testes de valores nas bordas (t=0,1) e monotonia onde aplicável.
2. Criar `core/transition.py` com as transições da tabela, plugáveis no `SceneManager` (`push(scene, transition="diag")`).
3. Atualizar componentes do `01_DESIGN_SYSTEM.md` para usar tokens de movimento.
4. Criar `systems/pulse.py` e ligar ao áudio (BPM) e ao backdrop.
5. Catálogo de SFX de UI + mixer "Interface" + opção "Reduzir movimento".
6. Ferramentas: `tools/transition_preview.py` grava sequência de quadros em PNG para revisão.

## 10. Critérios de aceite
- [ ] Toda mudança de tela usa uma transição do catálogo; nenhuma "troca seca".
- [ ] Ação → resposta visual ≤ 100 ms medida; sem bloqueio de entrada durante animações.
- [ ] "Reduzir movimento" remove deslizes/tremores em 100% das telas.
- [ ] Pulso sincronizado com a música em menu e hub; desliga nas opções.
- [ ] p95 do frame ≤ 16,7 ms em todas as telas no perfil "notebook fraco".

## 11. Riscos
- **Excesso de animação** cansa → teste de "uso repetido" (abrir/fechar 30 vezes) e ajuste de durações.
- **Enjoo/foto-sensibilidade** → respeitar opções, nenhum flash > 3 Hz, evitar tremor contínuo.
