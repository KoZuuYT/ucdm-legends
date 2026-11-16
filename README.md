# UCDM Legends

RPG de ação 2D com **treino + arena**, feito com os personagens do universo **UCDM**.
Python 3.10+ e **pygame-ce**: leve, roda em qualquer PC e está pronto para o mobile.

```bash
pip install -r requirements.txt
python main.py
```

| Atalho de dev | O que faz |
|---|---|
| `python main.py --skip-update` | pula a checagem de atualização |
| `python main.py --scene arena` | abre direto numa cena (`hub`, `arena`, `select`, `slash`, `shield`, `agility`, `focus`) |
| `python -m unittest discover -s tests -v` | testes headless (rodam no CI) |
| **F3** no jogo | FPS, uso de texturas e quantos objetos o culling desenhou |
| **F11** | tela cheia |
| **Esc** | pausa (treino/arena) e volta nas telas |

## Controles
| Ação | Teclado | Toque |
|---|---|---|
| Direções (treinos) | Setas / WASD | Deslizar ou botões na tela |
| Atacar / Defender (segurar) / Esquivar | J / K / L (ou Z / X / C, Shift) | Botões ATK / DEF / ESQ |
| Mira (treino de Foco) | Mouse | Tocar no alvo |

## Loop de jogo
1. **Treinos** (cada um sobe um atributo): Golpe → Força, Escudo → Defesa, Esquiva → Agilidade, Mira → Foco.
2. **Arena**: 8 desafiantes em sequência (até o chefe). Bloquear no instante exato = **PARRY** (atordoa o inimigo).
   Aviso **vermelho (!!)** = golpe imbloqueável: esquive.
3. **Ouro** das lutas e treinos melhora a arma.

## Saves, opções e ajuda
- **3 slots de save** (menu → *Saves*): jogar, novo jogo, renomear treinador, copiar para outro slot, exportar
  (`%APPDATA%\UCDM\exports\*.ucdmsave`), importar o arquivo mais recente dessa pasta e apagar (segure o botão para confirmar).
  O save antigo continua no Slot 1. Antes de migrar um save de formato antigo, o jogo guarda `slotN.vX.bak`.
- **Opções** (menu ou Campo de Treino): tela cheia, limite de FPS, volumes, **remapear teclas** (Esc é reservado),
  dificuldade (fácil/normal/difícil), aviso do golpe imbloqueável mais longo, pausar ao perder o foco e acessibilidade
  (intensidade dos efeitos, tremor, flashes, congelar no impacto e *reduzir movimento*). Só a chave alterada vai para `settings.json`.
- **Ajuda**: tutorial na primeira vez (pulável), *Ajuda* no Campo de Treino e **Estatísticas** (parries, esquivas, críticos, recordes, diário da arena).
- **Sons e músicas** são gerados por `python tools/make_sfx.py` (sem licença). Troque qualquer arquivo em `assets/audio/`
  ou aponte outro em `game.json → audio`.

## Arquitetura
```
core/        loop de timestep fixo, cenas em pilha, input abstrato (teclado/mouse/toque), display escalável, config, eventos, UI
entities/    Entity com componentes, Fighter (máquina de estados), IA data-driven, progressão, elenco
systems/     AssetManager (lazy + LRU + mods), culling (Camera + SpatialGrid), pooling, partículas, áudio, save
minigames/   treinos plugáveis (@register) sobre uma base comum
scenes/      boot/update, menu, seleção de personagem, hub, arena, overlays
network/     checagem de versão, download seguro e aplicação de updates via GitHub
installer/   instalador gráfico, desinstalador e patcher (só stdlib + tkinter) e o script que monta o Release
assets/      data/*.json (todo o balanceamento), sprites/, audio/, fonts/
tools/       import_characters.py, make_installer_art.py, make_sfx.py
```

**Desempenho**
- Lógica a 60 Hz fixos e renderização desacoplada. Escala feita na GPU (`SCALED`) com letterbox, sem distorção.
- Só o que está na tela é desenhado: a arena usa `SpatialGrid`, a seleção de personagem desenha só as linhas visíveis (aprox. 24 de 160).
- Sprites são reduzidos na importação e as versões escaladas ficam num cache LRU com limite de memória.
- Partículas, alvos e projéteis usam *pools*, então nada é alocado no meio do frame.

**Mobile**: o jogo só conhece *ações*. Toque e swipe viram as mesmas ações do teclado,
e cada cena declara seus botões virtuais, que aparecem automaticamente quando o jogador toca na tela.

## Conteúdo e mods
- **Personagens novos**: coloque os PNGs em `UCDM/` e rode `python tools/import_characters.py`.
  Nomes e o lado para onde a arte olha (`faces`) ficam editáveis em `assets/data/characters.json`.
- **Balanceamento**: `balance.json` (atributos, dano, parry, curvas de XP), `enemies.json` (desafiantes, ataques, IA)
  e `minigames.json` (duração e dificuldade dos treinos).
- **Sons e música**: coloque arquivos `.ogg` nos caminhos listados em `game.json → audio`. Se faltar algum arquivo, o jogo continua em silêncio.
- **Fundos**: o arquivo `assets/sprites/backgrounds/<tema>.png` (`meadow`, `dusk`, `arena`, `night`) substitui o fundo procedural.
- **Mods sem mexer na instalação**: crie `%APPDATA%/UCDM/mods/<nome>/assets/...`, que sobrepõe qualquer asset,
  e `.../data/*.json`, que é mesclado por cima da configuração oficial.

## Atualizações automáticas e Releases (GitHub)
**Configuração (uma vez só)**
1. Crie um repositório **público** e suba o projeto (a pasta `UCDM/` com as artes originais fica fora, pelo `.gitignore`).
2. Em `assets/data/game.json → update.repo`, coloque `seu_usuario/seu_repo`. O build do Release também preenche isso automaticamente.

**Publicar uma versão nova**
```bash
# 1. mude "version" (e "notes") em version.json, faça commit e push
git tag v0.2.0
git push origin main v0.2.0
```
O workflow `.github/workflows/release.yml` roda os testes, compila `UCDM.exe` (onedir) e `UCDM-Installer.exe`
e publica no Release `UCDM-windows-v0.2.0.zip` junto com o `.sha256`.

**O que acontece na máquina do jogador**
- **Instalar**: o jogador baixa só o `UCDM-Installer.exe`. O assistente mostra a versão e as notas do último Release e deixa escolher:
  - pasta (padrão `%LOCALAPPDATA%\Programs\UCDM`, com espaço livre conferido);
  - atalhos na Área de Trabalho e no Menu Iniciar;
  - registro em "Aplicativos instalados";
  - tela cheia ou janela, limite de FPS, VSync, contador de FPS, volumes e atualizações automáticas.

  As preferências vão para `%APPDATA%\UCDM\settings.json`, que o jogo mescla por cima de `game.json`.
- **Desinstalar**: pelas Configurações do Windows ou com `UCDM-Installer.exe --uninstall`. Os saves são mantidos, a menos que o jogador marque para apagar.
- **Sem janela**: `UCDM-Installer.exe --silent [--dir PASTA] [--no-shortcut] [--no-register]`, com log em `%TEMP%\ucdm-installer.log`.
- **Erros do jogo**: ficam em `%APPDATA%\UCDM\logs\` (`game.log` e `crash.log`), e o jogo mostra um aviso em vez de fechar sem explicação.
- **Atualizar**: no boot, o jogo compara o `version.json` local com o do GitHub. Se houver versão nova, ele baixa,
  confere o hash, prepara os arquivos, fecha e o patcher troca os arquivos e reabre o jogo.
  Os saves ficam em `%APPDATA%\UCDM` e nunca são tocados. Sem internet, o jogo abre normalmente.
- **Segurança**: só aceita HTTPS de domínios do GitHub, verifica o checksum e bloqueia caminhos perigosos dentro do zip ("zip slip").
- Rodando pelo código-fonte, o update **não** sobrescreve o repositório (só avisa que há versão nova).
