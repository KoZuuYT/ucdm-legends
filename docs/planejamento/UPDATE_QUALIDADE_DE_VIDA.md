# UCDM Legends: Update "Qualidade de Vida"

Objetivo: tirar atrito do dia a dia do jogador. Menos clique perdido, menos medo de apagar
progresso, mais controle sobre o jogo (saves, opções, teclas, acessibilidade) e informação clara
sobre o que está acontecendo.

> **Status (v0.2.0, sem release publicada):** implementado: 3 slots com seletor (renomear, copiar, exportar/importar,
> apagar segurando o botão), backup por versão e recuperação pelo `.bak`, indicador "Salvo", tela de Opções
> (vídeo, áudio, rebind de teclas, dificuldade, aviso estendido, acessibilidade), pausa (Esc e perda de foco),
> saída com confirmação, tutorial da primeira vez + Ajuda, estatísticas, recordes e diário da arena, créditos.
> **Ficou para depois:** atualização em segundo plano, notas da versão no menu, verificação de integridade dos assets,
> botão "copiar informações do sistema", modo de baixo desempenho, tamanho de texto/paleta daltônica/alto contraste,
> idiomas, "Treinar de novo" no hub, navegação por gamepad e confirmar "Novo jogo" sobre slot usado (o seletor só
> permite novo jogo em slot vazio, então a sobrescrita não acontece). Importar usa o arquivo mais recente de `exports/`.

Planejamento original:

---

## 0. Diagnóstico do estado atual (v0.1.2)

| Ponto de atrito | Onde está | Efeito para o jogador |
|---|---|---|
| **Só existe um save** (`slot1.json`) | `systems/save.py` (`SaveManager(slot="slot1")`) | Não dá para ter dois personagens ou testar sem perder o progresso |
| **"Novo jogo" sobrescreve o save** sem aviso | `scenes/menu.py` (`_new`) | Perda de progresso por um clique |
| **Sem tela de opções no jogo** | `scenes/menu.py` só tem Continuar / Novo jogo / Sair | Volume, tela cheia, FPS e teclas só mudam editando JSON ou pelo instalador |
| **Teclas fixas** | `assets/data/game.json → input` | Não é possível rebind; só via editar o JSON |
| **"Sair" fecha na hora** | `scenes/menu.py` (`self.game.quit`) | Sem confirmação; em partida, não há como voltar sem perder o ponto |
| **Sem pausa** | `scenes/arena.py`, minigames | Não dá para parar uma luta para ir ao menu |
| **Sem indicação de salvamento** | `systems/save.py` salva em silêncio | O jogador não sabe se o progresso foi gravado |
| **Mensagens de erro vão para o log** | `core/paths.py`, `main.py` (`crash.log`) | Ninguém vê o log; o jogador fica sem saber o que fazer |
| **Tutorial inexistente** | Só o README | Primeira vez confusa (o que é PARRY? o que é !!?) |
| **Atualização só no boot** | `network/updater.py` | Quem deixa o jogo aberto nunca vê a nova versão |
| **Sem histórico/estatísticas** | `entities/progression.py` | Não há noção de quanto o jogador já evoluiu |
| **Sem "ir direto" para treino ou arena** | `scenes/hub.py` | Muitos cliques para voltar à luta |

---

## 1. Princípios

1. **Nada se perde sem aviso.** Qualquer ação destrutiva (apagar save, sobrescrever, redefinir
   atributos) pede confirmação, com a opção padrão sendo "cancelar".
2. **Configuração no jogo.** Todo ajuste que hoje exige editar JSON ganha tela própria. O JSON
   continua valendo para quem quer avançar, e os valores são os mesmos.
3. **Compatibilidade total.** Saves e `settings.json` antigos continuam abrindo. Migrações passam
   por `SaveManager._migrate` e `core/config.py`.
4. **Ações, não teclas.** Já é assim no projeto (o jogo conhece ações; teclado, mouse e toque são
   mapeados). O rebind de teclas só mexe no mapa de ações, sem tocar na lógica.
5. **Todo recurso novo tem valor padrão seguro.** Se algo falhar, o jogo cai no padrão e registra
   no log, sem fechar.

---

## 2. Funções por área

### 2.1 Saves e perfis
- [ ] **Seletor de saves** com 3 slots (`slot1`, `slot2`, `slot3`). Cada slot mostra: nome do
      lutador, nível total, arena alcançada, horas jogadas e data do último save.
- [ ] **Renomear slot** (nome do treinador, até 16 caracteres).
- [ ] **Apagar slot** com confirmação em duas etapas (digitar "APAGAR" ou segurar o botão por 1,5 s).
- [ ] **Copiar slot** (duplica o save para outro slot, útil para testar builds).
- [ ] **Exportar / importar save** para um arquivo `.ucdmsave` (JSON com `save_version`), na pasta
      de saves do usuário. Facilita backup e troca entre PCs.
- [ ] **Backup automático** antes de migrar de versão (`slotN.v<versão>.bak`, mantendo os 3 últimos).
- [ ] **Autosave** ao fim de cada treino, luta e ao sair do hub, com indicador "Salvo ✓" no canto.
- [ ] **"Novo jogo" pede confirmação** quando já existe save naquele slot. Se o slot estiver vazio,
      não pede.
- [ ] **Recuperação**: se o save principal estiver corrompido, oferece usar o `.bak` com aviso claro,
      em vez de só ignorar.

**Mudanças técnicas:**
- `SaveManager(slot)` já aceita o nome do slot; falta um `SaveIndex` que lê o resumo de cada slot
  sem carregar o save inteiro.
- `core/paths.py` ganha `SAVE_SLOTS = ["slot1", "slot2", "slot3"]`.
- Nova cena `scenes/save_select.py`, aberta por "Continuar" (ou por "Jogar" quando há mais de um slot).

### 2.2 Menu e navegação
- [ ] **Tela de Opções** no menu principal e acessível por Esc no hub (ver 2.3).
- [ ] **Tela de Créditos** (versão, equipe, bibliotecas usadas, licenças de fontes e sons).
- [ ] **Sair com confirmação** ("Sair do jogo? O progresso já está salvo.").
- [ ] **Atalhos no hub**: "Treinar de novo" (repete o último treino), "Arena agora" (vai direto ao próximo desafiante).
- [ ] **Voltar com Esc/Backspace** em todas as telas, incluindo seleção de personagem e resultados
      (hoje nem todas respondem).
- [ ] **Navegação completa por teclado e gamepad** em todos os menus (foco visível, ordem lógica).
- [ ] **Dicas de carregamento** e **tooltips** curtos ao passar o mouse ou focar um botão
      (ex.: "PARRY: bloqueie no instante exato para atordoar o inimigo").

### 2.3 Opções (novo, o mais importante do update)
Tela `scenes/options.py` com abas:

**Vídeo**
- [ ] Tela cheia / janela (já existe com F11; vira opção persistente).
- [ ] Escala: pixel-perfect ou suave (`SCALED` já existe; falta a escolha).
- [ ] Limite de FPS (30, 60, 120, 144, ilimitado) e VSync.
- [ ] Contador de FPS (F3 vira opção, não só atalho).
- [ ] Brilho/gama simples (opcional; só se o custo for baixo).

**Áudio**
- [ ] Volume geral, música, efeitos (já existem em `game.json`; viram sliders).
- [ ] Mudo quando a janela perde foco (opção).
- [ ] Teste de som ao soltar o slider de efeitos.

**Controles**
- [ ] **Rebind de teclas** por ação (`left`, `right`, `attack`, `block`, `dodge`, `confirm`, `back`).
      Clicar na ação, pressionar a nova tecla. Detectar conflito e perguntar se quer trocar.
- [ ] Duas teclas por ação (principal e alternativa), como já existe no JSON.
- [ ] Restaurar padrão por ação e geral.
- [ ] Sensibilidade do mouse (para treino de Foco) e tamanho dos alvos de toque.

**Jogo / Acessibilidade**
- [ ] Idioma (preparar a estrutura; PT-BR continua o padrão).
- [ ] Tamanho do texto (pequeno, normal, grande).
- [ ] Alto contraste nos avisos (!!) e nas barras de vida.
- [ ] Cores daltônicas: paleta alternativa para os atributos (força, defesa, agilidade, foco) e
      marcadores com forma, não só cor.
- [ ] **Reduzir movimento** (desliga shake, zoom e tremor; depende do update de Visual, seção 4).
- [ ] **Dificuldade**: fácil / normal / difícil, ajustando dano sofrido e janela de parry.
      Multiplicadores em `balance.json`, sem duplicar valores.
- [ ] Tempo de aviso de golpe imbloqueável (!!): normal ou estendido (+50%).
- [ ] Mostrar/esconder dicas de tutorial.

**Persistência:** tudo grava em `%APPDATA%/UCDM/settings.json`, que já é mesclado sobre `game.json`
(`core/config.py`). Mudança de tela cheia e de FPS aplica na hora, sem reiniciar.

### 2.4 Tutorial e ajuda
- [ ] **Primeira vez**: tutorial curto (3 passos) antes do primeiro treino: movimento, ataque,
      bloqueio/parry. Pode ser pulado e revisto em Opções → Ajuda.
- [ ] **Glossário** (Opções → Ajuda): PARRY, !!, esquiva, atributos, arma, ouro.
- [ ] **Overlay de controles** (tecla H ou `?`) mostrando as teclas atuais, já com o rebind aplicado.
- [ ] **Explicação de atributos** ao focar o botão de treino: o que cada um melhora.

### 2.5 Pausa e fluxo de partida
- [ ] **Pausa** (Esc durante treino ou arena): Continuar / Opções / Desistir / Menu principal.
      "Desistir" de arena pede confirmação e não gasta a chance de revanche.
- [ ] **Pausa automática** ao perder o foco da janela (opção ligada por padrão).
- [ ] **Resultado de treino** com resumo claro: o que subiu, quanto ouro e XP ganhou, e atalho
      "Treinar de novo".
- [ ] **Tempo de jogo** registrado no save (mostrado no seletor de saves).

### 2.6 Informação e progresso
- [ ] **Estatísticas do treinador**: lutas vencidas, parries, críticos, esquivas bem-sucedidas,
      melhor sequência de vitórias, tempo total. Tela própria, acessível do hub.
- [ ] **Diário de arena**: lista dos 8 desafiantes, com derrota/vitória e o que cada um ensina.
- [ ] **Recordes** (melhor tempo de treino de Foco, maior dano em um golpe).
- [ ] Os dados vêm de `entities/progression.py` e são gravados no save; sem coleta externa.

### 2.7 Atualização e avisos
- [ ] **Checagem de atualização em segundo plano** (a cada 30 min com o jogo aberto), com aviso
      discreto no menu: "Versão X disponível. Reinicie para atualizar."
- [ ] **Aviso de atualização não obrigatória**: o jogador escolhe quando reiniciar. A atualização
      automática no boot continua como padrão.
- [ ] **Notas da versão** no menu, na primeira execução após atualizar ("Novidades em v0.2.0").
- [ ] **Relatório de erro amigável**: ao falhar, mostrar caminho do `crash.log` e botão "Abrir pasta de logs".
- [ ] **Verificar integridade dos arquivos** (hash dos assets), com opção de reparar sem apagar saves.

### 2.8 Desempenho e diagnóstico
- [ ] Painel de diagnóstico (F3 expandido): FPS, tempo de frame, objetos, memória de texturas, versão.
- [ ] Botão "Copiar informações do sistema" para anexar em relatos de bug (sem dados pessoais:
      sem nome de usuário do Windows nem caminhos completos, só a versão do jogo e do sistema).
- [ ] Modo de baixo desempenho: reduz partículas, fundos animados e sombras, com um clique.

---

## 3. Fases de implementação

### Fase 1: Saves e segurança de progresso (prioridade máxima)
- [ ] `SaveIndex` com resumo de cada slot.
- [ ] Três slots, renomear, apagar com confirmação dupla, copiar.
- [ ] Confirmação ao sobrescrever com "Novo jogo".
- [ ] Backup por versão e recuperação a partir do `.bak` com aviso.
- [ ] Exportar/importar `.ucdmsave`.
- [ ] Testes: `test_save_slots_isolated`, `test_new_game_requires_confirm_when_slot_used`,
      `test_corrupt_main_falls_back_to_bak`, `test_export_import_roundtrip`.

**Critério de saída:** nenhum caminho de código apaga um save sem passar por confirmação.

### Fase 2: Opções e controles
- [ ] Cena `scenes/options.py` com abas Vídeo, Áudio, Controles, Jogo.
- [ ] Gravação em `settings.json` com `deep_merge` (já existe em `core/config.py`).
- [ ] Rebind de teclas com detecção de conflito e restaurar padrão.
- [ ] Aplicar FPS, tela cheia e volumes na hora.
- [ ] Testes: `test_rebind_conflict_detected`, `test_settings_write_is_partial`,
      `test_restore_defaults_removes_overrides`.

**Critério de saída:** nenhuma opção comum exige editar JSON.

### Fase 3: Fluxo de partida e pausa
- [ ] Pausa em treino e arena, com Esc e foco de janela.
- [ ] Desistir com confirmação.
- [ ] Autosave com indicador "Salvo ✓".
- [ ] Atalhos "Treinar de novo" e "Arena agora" no hub.
- [ ] Voltar com Esc em todas as telas.

### Fase 4: Ajuda e tutorial
- [ ] Tutorial da primeira vez (pulável, revisitável).
- [ ] Glossário e overlay de controles (H).
- [ ] Tooltips curtos nos botões.
- [ ] Dicas de carregamento.

### Fase 5: Acessibilidade e dificuldade
- [ ] Dificuldade (fácil/normal/difícil) via `balance.json` e `settings.json`.
- [ ] Tamanho de texto, alto contraste, paleta para daltonismo.
- [ ] Tempo estendido para o aviso !!.
- [ ] Reduzir movimento (depende do update Visual, Fase 1 e 2 dele).
- [ ] Navegação completa por teclado e gamepad.

### Fase 6: Informação, progresso e atualização
- [ ] Estatísticas do treinador e diário de arena.
- [ ] Recordes.
- [ ] Checagem de atualização em segundo plano com aviso não obrigatório.
- [ ] Novidades da versão na primeira execução.
- [ ] Relatório de erro amigável e copiar informações do sistema.
- [ ] Verificação de integridade dos assets com reparo sem apagar saves.

### Fase 7: Diagnóstico e desempenho
- [ ] F3 expandido e modo de baixo desempenho.
- [ ] Revisão final: rodar tudo com saves antigos (v0.1.0, v0.1.2) para garantir compatibilidade.

---

## 4. Dependências e conflitos com o update Visual

- **Tela de opções** depende de `core/ui.py` (botões, sliders novos). O update Visual muda os mesmos
  botões (animações de foco). Recomendo criar os widgets de slider e toggle **uma vez**, no
  Fase 2 deste update, e o update Visual reaproveita.
- **Reduzir movimento** só faz sentido depois que `feedback.json` existir (Fase 1 do Visual).
- **Seletor de saves** usa `scenes/character_select.py` para novos personagens; as duas mudanças
  mexem na mesma cena de fluxo de "Novo jogo". Fazer a Fase 1 deste update antes da troca de
  transições do Visual.
- **Pausa** e **resultados** usam `core/scene.py` (pilha de cenas). A troca de transições do
  Visual (`kind=`) deve manter o padrão atual, para não quebrar o pop com overlay.

---

## 5. Testes e validação

**Automáticos (`tests/`)**, além dos 12 atuais:
- Saves: isolamento entre slots, confirmação de sobrescrita, recuperação a partir do `.bak`,
  export/import com `save_version`.
- Configurações: escrita parcial sem apagar outras chaves, restaurar padrão, validação de valores
  inválidos (FPS negativo, volume acima de 1, tecla vazia).
- Rebind: conflito detectado, par de teclas principal/alternativa.
- Migração: save da v0.1.0 abre na v0.2.x sem perda de atributos.
- Atualização em segundo plano: não reinicia sozinha; só avisa.

**Manuais (checklist por fase):**
- Criar três saves, renomear, copiar, apagar, sem perder os outros.
- Matar o jogo no meio de um treino e conferir o último autosave.
- Rebind de todas as teclas e voltar a tecla padrão.
- Abrir o jogo com `settings.json` corrompido e ver o aviso, sem crash.
- Jogar sem mouse e sem som, só teclado.

---

## 6. Decisões que dependem de você

1. **Quantos slots?** Proposta: 3. Pode ser 5 se quiser mais liberdade para testes.
2. **Exportar save:** o arquivo `.ucdmsave` é JSON legível. Aceitável, ou prefere formato binário/
   com assinatura para evitar edição de atributos?
3. **Dificuldade:** a dificuldade deve afetar também as recompensas de XP/ouro, ou só o desafio?
4. **Estatísticas:** guardar apenas no save local, ou quer também exibir um resumo no README/Release?
5. **Atualização em segundo plano:** aceitável que o jogo baixe a atualização enquanto roda (sem
   instalar até o jogador reiniciar), ou só avisa e espera a próxima abertura?
6. **Idiomas:** só PT-BR por enquanto, com estrutura para inglês, ou já traduzir?

---

## 7. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Saves multi-slot quebrarem saves atuais | alto | slot1 continua sendo o atual; migração e teste com saves reais antes da release |
| Rebind deixar o jogo sem como sair (Esc remapeado) | alto | Esc e "voltar" nunca podem ser removidos; o rebind recusa essas teclas |
| Atualização em segundo plano corromper arquivos em uso | alto | só baixa e confere hash; aplicar apenas no reinício, pelo patcher atual |
| Muitas telas novas aumentarem o tempo de manutenção | médio | widgets compartilhados (slider, toggle, lista de slots) |
| Dificuldade quebrar o balanceamento | médio | multiplicadores pequenos e testados com a arena inteira |

---

## 8. Versionamento e entrega

- Proposta: **v0.3.0** ("Qualidade de Vida"), com Fases 1 a 4. Acessibilidade e estatísticas
  (Fases 5 e 6) podem sair na v0.3.1.
- Se o update Visual sair antes (v0.2.0), este começa em v0.3.0 sem mudança de formato de save.
- Cada fase vira um commit em português. Tag só depois do checklist da seção 5.
- Jogadores que já têm a v0.1.x instalada recebem a atualização pelo mecanismo atual. Isso exige
  que a v0.1.0 instale o novo `UCDM-Installer.exe` uma vez (ver nota no README e na v0.1.2).
- A notas do Release devem avisar que o save antigo vira o **slot 1** e não é alterado.
