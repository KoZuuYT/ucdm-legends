# 06 — Resultados, Pausa, Diálogos, Toasts e Conquistas

**Versão alvo:** 0.7.0 · **Arquivos:** `scenes/results.py`, `scenes/pause.py`, `scenes/dialogs.py`, `core/feedback.py`, `systems/achievements.py` (novo)
**Assets Minecraft:** ver `10_MINECRAFT_ASSETS.md` §5.6 (toasts de avanço, árvore de conquistas, orbes de XP, itens como recompensa).

## 1. Objetivo
Telas que fecham o ciclo emocional (vitória/derrota) e telas utilitárias (pausa, confirmações) rápidas, claras e com identidade.

## 2. Resultados (pós-luta)
**Vitória (~4 s, `Enter` acelera):**
1. Faixa dourada diagonal "VITÓRIA" carimbada + confete.
2. Placar em linhas (stagger 0,18 s) com contador animado e som crescente: tempo, dano causado/recebido, parries, esquivas perfeitas, contra-ataques, armaduras quebradas.
3. **Nota S–D** (estilo/eficiência) carimbada; nota S com brilho encantado e livro encantado como ícone.
4. **Recompensas**: ouro base + bônus de estilo (já existe) listados separadamente; esmeraldas/moedas e **orbes de XP** voam até o contador; selo "NOVO RECORDE".
5. Conquistas/desbloqueios surgem como toasts de avanço.
6. Botões: **Próxima luta** (primário), Hub, Repetir, Estatísticas.

**Derrota:** tom sóbrio (dessaturado, faixa `hot`), **"o que aprender"** com 1–2 dicas calculadas dos números ("Você levou 6 golpes laranja — apare ou esquive"; "14 ataques sem pausa — a fadiga reduziu seu dano"). Primário: **Tentar de novo** (1 tecla).
**Extras:** comparação com o melhor resultado (▲▼ com texto, não só cor); copiar resultado como texto; opção "Resultados rápidos".

## 3. Pausa
- Abre em 0,15 s: jogo congela, fundo desfocado/escurecido (snapshot 1/4), painel lateral desliza.
- Itens: Continuar · Reiniciar luta · Opções · Ajuda (controles/regras) · Voltar ao hub · Menu principal.
- Resumo da luta (tempo, vida) + lembrete de controles com ícones do dispositivo ativo.
- Confirmação só quando há progresso a perder; "pausa por perda de foco" mostra aviso; contagem 3-2-1 opcional ao continuar.

## 4. Diálogos e modais
- Painel central, título em faixa, texto com quebra automática, ícone de contexto; variantes: confirmar, **destrutiva (segurar para confirmar)**, informativa, múltipla escolha, **entrada de texto** (renomear), **progresso** (atualização/integridade).
- Foco preso, `Esc` cancela, `Enter` = primário (nunca o destrutivo).
- Botões com verbos ("Apagar save", "Manter"), nunca "OK/Cancelar" genérico; textos medidos e traduzidos.
- Erros: mensagem humana + "Mostrar detalhes" + "Copiar relatório".

## 5. Toasts
- Fila com prioridade (info, sucesso, aviso, erro, conquista), máx. 3 visíveis, entrada lateral `back_out`, barra de tempo, ação opcional ("Desfazer").
- Conquistas não interrompem a luta: ficam na fila e saem no resultado. Hover pausa o tempo.

## 6. Conquistas (novo)
- ~30 em `assets/data/achievements.json` (id, nome, descrição, ícone de item, condição, secreta?): *Primeiro Sangue*, *Mestre do Parry* (10 parries numa luta), *Intocável*, *Sem Pressa* (sem spam), *Colecionador* (20 personagens), *Armadura Quebrada* (50), *Chefe Derrubado*, *Rodada Perfeita*.
- Tela em formato de **árvore de avanços**: nós ligados por linhas, molduras tarefa/objetivo/desafio, progresso e "???" para secretas.
- `systems/achievements.py` escuta o barramento `core/events.py`, persiste no save, não duplica. Recompensas **cosméticas** (molduras, cores), nunca vantagem de combate.

## 7. Dados
`results.json` (pesos da nota, limites S–D, regras de dicas), `achievements.json`, strings PT/EN.

## 8. Implementação
1. `results.py` em timeline (`Seq`) com `StatRow` reutilizável.
2. Função pura `analyze(stats) -> nota, dicas` (testável).
3. `pause.py` com painel lateral; `dialogs.py` como fábrica (`Dialog.confirm/destructive/info/input/progress`).
4. Fila de toasts + `achievements.py`.

## 9. Testes
`analyze` com entradas sintéticas; conquistas disparam 1× e persistem; diálogos (foco preso, `Esc`, segurar-para-confirmar, limite de texto); capturas de vitória/derrota (nota S e D), pausa e 5 diálogos em PT/EN.

## 10. Critérios de aceite
- [ ] Resultado completo legível com e sem animação.
- [ ] Derrota sempre dá uma dica útil e "Tentar de novo" em 1 ação.
- [ ] Ações destrutivas nunca por clique acidental.
- [ ] Conquistas persistem e nunca aparecem em plena luta.

## 11. Riscos
Resultados longos irritam → `Enter` pula e "Resultados rápidos". Dicas erradas frustram → regras conservadoras validadas com logs da simulação.
