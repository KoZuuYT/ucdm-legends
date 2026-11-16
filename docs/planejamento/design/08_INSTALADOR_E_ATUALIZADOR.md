# 08 — Instalador, Atualizador e Marca

**Versão alvo:** 0.8.0 · **Arquivos:** `installer/gui.py`, `installer/setup_core.py`, `installer/art/`, `scenes/news.py`, `core/updater` (módulo de atualização), ícone `assets/sprites/ui/icon.png`
**Assets Minecraft:** `10_MINECRAFT_ASSETS.md` §5.8 (fundo de terra/pedra, barra de XP, botões 9-slice) — **sujeito à decisão de licença**.

## 1. Objetivo
O instalador e o atualizador são o **primeiro contato** com o jogo. Devem ser bonitos, claros, confiáveis (SHA-256, sem surpresas) e coerentes com a identidade do jogo.

## 2. Instalador gráfico
### Fluxo (5 passos, com indicador de etapas em faixa)
1. **Boas-vindas**: logo carimbado, versão, "projeto de fãs", botão Avançar; seletor de idioma (PT/EN) no canto.
2. **Licença e avisos**: texto rolável (licenças de terceiros), checkbox "Li e aceito" (obrigatório para continuar).
3. **Opções**: pasta de instalação (com validação e espaço necessário/livre), atalhos (área de trabalho/menu iniciar), "iniciar com o Windows" (desligado), tipo de instalação (**Padrão / Personalizada**: pacote de áudio, pacote de idiomas, tema Minecraft se existir).
4. **Instalando**: barra grande (estilo "barra de XP" no tema Minecraft ou "fita de pontuação" no tema Torneio), arquivo atual, velocidade, tempo restante, dicas de jogo rotativas; **Cancelar** seguro (limpa o que fez).
5. **Concluído**: resumo, "Iniciar o jogo", "Abrir pasta", "Ver novidades"; confete leve; botão "Copiar log" se houve aviso.
- Tela de **erro amigável** com causa provável (sem permissão, disco cheio, antivírus) e ação ("Escolher outra pasta", "Tentar de novo", "Copiar relatório").
- Verificação **SHA-256** de cada arquivo baixado/extraído, com mensagem clara em caso de falha e repetição automática (3 tentativas).
- **Reparar / Desinstalar** como modos (mesmo executável): reparar revalida arquivos; desinstalar pergunta se mantém saves e remove atalhos/registro.
- Acessibilidade: teclado completo, contraste alto, escala de DPI correta (Windows), texto ≥ 14 pt.

### Visual
- Janela sem moldura nativa opcional com barra própria (arrastável), cantos chanfrados e faixa diagonal no topo; fundo com ruído de papel/halftone e silhuetas de personagens em parallax suave.
- Botões do design system (01) — portar a lib de componentes para uma variante **leve** (sem dependência do jogo) ou reusar `core/ui` empacotado.
- Animação de abertura curta (logo carimbado) e transições de passo por deslize (0,25 s).

## 3. Atualizador (no jogo e no instalador)
- Verificação em segundo plano (já existe): resultado como **ponto de notificação** no menu e toast, nunca interrompe uma luta.
- **Tela de atualização** (modal): versão atual → nova, **o que mudou** (notas formatadas em cartões, do `version.json`/release), tamanho do download, botões "Atualizar agora / Depois / Ignorar esta versão".
- Download com barra, velocidade e **pausar/retomar**; verifica SHA-256; aplica ao fechar o jogo; **reinicia** automaticamente; mantém saves e settings; **rollback** automático se a nova versão falhar ao abrir (mantém a anterior por 1 versão).
- Canais: **Estável** (padrão) e **Prévia** (opcional, em Opções).
- Falhas de rede: mensagem amigável e "Tentar de novo"; modo offline sem erros.
- Segurança: apenas URLs do repositório configurado, hash obrigatório, nada executado antes da verificação (já seguido).

## 4. Marca e ícones
- **Ícone do app** em múltiplos tamanhos (16/32/48/64/128/256) com um símbolo reconhecível (ex.: punho/escudo dentro de formato chanfrado), versão em pixel-art para o tema Minecraft; `.ico` multi-resolução gerado por script (`tools/make_icons.py`).
- **Informações de versão** nos `.exe` (já feitas) e imagem do instalador (banner lateral 164×314 se usar NSIS/Inno no futuro).
- **Social preview** do GitHub (1280×640), capturas do README e GIFs curtos (`tools/make_gif.py`).
- Página de Release com notas padronizadas (template no CI) e imagem de capa.

## 4.1 Pacote de fontes e licenças
`installer/` embute as fontes OFL e lista atribuições no passo 2; um arquivo `LICENSES/` é copiado para a instalação.

## 5. Implementação
1. Refatorar `installer/gui.py` em **passos** (`StepWelcome`, `StepLicense`, `StepOptions`, `StepInstall`, `StepDone`) com navegação e validação.
2. Componentes visuais compartilhados (botão, barra, indicador de etapas) em `installer/ui_lite.py`.
3. Modos Reparar/Desinstalar; log em arquivo; relatório copiável.
4. Atualizador: modal, pausar/retomar, rollback, canais; testes com servidor local simulado (já usamos `rt.get_text` mockado).
5. Scripts de ícone/preview e template de release no workflow.

## 6. Testes
Instalação em pasta com espaço/acento (`D:\usuario alternativo\...`), sem permissão, disco cheio simulado, hash inválido, cancelamento no meio, reparar após apagar arquivo, desinstalar mantendo/removendo saves, atualização com falha e rollback; DPI 100/150/200%; teclado apenas.

## 7. Critérios de aceite
- [ ] Instalação padrão em ≤ 4 cliques; personalizada clara.
- [ ] Nenhuma falha deixa a instalação em estado corrompido (rollback/limpeza).
- [ ] Atualização preserva saves/settings e volta atrás se a versão nova não abrir.
- [ ] Visual consistente com o jogo em PT/EN e DPI altos.

## 8. Riscos
Usar a mesma lib de UI do jogo aumenta o tamanho do instalador → variante leve. Assets de terceiros no instalador exigem atenção de **licença** (ver `10_MINECRAFT_ASSETS.md` §11).
