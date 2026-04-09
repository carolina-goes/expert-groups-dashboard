# Dashboard - Registo de Grupos de Peritos da Comissao Europeia

Dashboard interativo com atualizacao automatica diaria dos dados do Registo de Grupos de Peritos da Comissao Europeia.

## Aceder ao Dashboard

**Abra este link no browser:** [carolina-goes.github.io/expert-groups-dashboard](https://carolina-goes.github.io/expert-groups-dashboard/)

## Funcionalidades

- Pesquisa por texto livre (nome, codigo, missao)
- Filtros: Estado, Tipo, DG Lider, Area de Politica, Tarefa, Formal/Informal
- 4 graficos interativos (Chart.js)
- Tabela ordenavel com paginacao (50 registos por pagina)
- Painel de detalhe com todos os campos ao clicar numa linha
- Exportacao CSV e JSON dos dados filtrados
- ~2039 grupos de peritos com 21 campos cada

## Atualizacao de Dados

Os dados sao atualizados automaticamente todos os dias as 07:00 (hora de Lisboa) atraves do GitHub Actions.

Para atualizar manualmente:
1. Ir ao separador **Actions**
2. Clicar em **Update Expert Groups Dashboard**
3. Clicar em **Run workflow**

## Fonte dos Dados

- **API:** Registo de Grupos de Peritos da Comissao Europeia
- **Licenca:** Decisao da Comissao 2011/833/UE (reutilizacao livre com atribuicao)

## Desenvolvido para

DCIRI/DSSD/SGGov - Portugal
