# Apostas Agentes

Equipa de agentes para analisar jogos de futebol das 10 ligas principais e decidir as apostas do dia, com júri e presidente.

## Como usar (hoje)
1. Descompacta o zip e abre um terminal na pasta `apostas-agentes`.
2. Corre `claude` (Claude Code).
3. Escreve `/dia` (ou "analisa os jogos de hoje").
4. No fim lês `jogos/AAAA-MM-DD/decisao.md`. A aposta colocas tu, na tua casa.

Para um só jogo: `/dia Benfica vs Porto`.

## Painel (Sala de Análise)
Noutro terminal, na mesma pasta, corre `python scripts/dashboard.py` e abre http://localhost:8765. Tem um botão **▶ Iniciar análise** (escolhe o dia completo ou só um jogo) e um botão **■ Parar**, por isso não precisas de escrever `/dia` à mão. Mostra cada agente (à espera, a trabalhar, concluído), o progresso por jogo, os votos do júri e a decisão do presidente, em tempo real. Clica num cartão para ler o relatório desse agente. O botão **◈ Ver demonstração** mostra os agentes a trabalhar com dados fictícios, sem gastar nada.

## Estrutura
- `CLAUDE.md`: fluxo do coordenador.
- `limites.md`: banca, stake, limites diários. **Edita antes de usar.**
- `.claude/agents/`: 6 especialistas, construtor, 4 membros do júri e presidente.
- `scripts/jogos_hoje.py`: lista os jogos do dia (sem chave de API).

## Notas
- Sem chaves de API os agentes usam pesquisa web, por isso a qualidade das odds e estatísticas varia. Para mais fiabilidade liga API-Football e The Odds API.
- Começa só a **simular** (anota as apostas sem dinheiro) durante 2 a 4 semanas e vê se a análise tem valor.
- Jogo responsável: define limites, nunca recuperes perdas. Apoio em Portugal: SICAD, linha 1414.
