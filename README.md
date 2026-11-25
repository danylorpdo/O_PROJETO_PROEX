# PROEX · Mineração de dados em acidentes rodoviários

Projeto de **Danylo Oliveira**, do curso de Engenharia de Software do Centro Universitário Fundação Assis Gurgacz (FAG).

O projeto analisa acidentes registrados pela Polícia Rodoviária Federal (PRF) no Paraná entre 2023 e 2025. O objetivo é identificar fatores associados à gravidade, verificar se as regras de associação se repetem em outro ano e avaliar a contribuição dos atributos municipais do IBGE. Cada linha representa uma ocorrência. A classe grave exige pelo menos uma vítima morta ou gravemente ferida.

## Metodologia KDD

1. **Seleção e preparação.** Leitura dos arquivos oficiais da PRF agrupados por ocorrência, recorte do Paraná, conferência dos identificadores e construção do alvo.
2. **Transformação e integração.** Vinculação por UF e nome normalizado ao código municipal do IBGE, com junção à esquerda e conferência com a malha municipal de 2022. População, área, densidade e proporção urbana do Censo 2022 formam a referência fixa.
3. **Mineração e avaliação.** Apriori com descoberta em 2023–2024 e verificação de suporte, confiança e lift em 2025. A classificação compara referência majoritária, Regressão Logística, Árvore de Decisão e Random Forest com e sem atributos do IBGE. O treino usa 2023, a validação usa 2024 e o teste final usa 2025.
4. **Interpretação.** Cruzamentos, métricas, matrizes de confusão e regras são disponibilizados em CSV, figuras e dashboard. Os resultados descrevem associações entre ocorrências registradas. Estimar exposição ao tráfego exigiria dados de circulação.

**Tecnologias:** Python 3.12, pandas, scikit-learn, Matplotlib, Shapely, PyShp, Streamlit, Plotly e pytest.

## Principais resultados

- **213.497** registros nacionais da PRF, dos quais **22.323** no Paraná. Foram **5.864 acidentes graves (26,27%)** e **16.459 não graves**.
- O vínculo nominal cobriu **100% das ocorrências**, em **158 municípios**. A conferência espacial encontrou 1.290 coordenadas em município diferente do declarado e 47 fora da malha de 2022. A integração usou o município declarado e registrou as divergências.
- A proporção de graves foi de **32,7%** em municípios abaixo de 25 habitantes por km² e de **20,7%** a partir de 500 habitantes por km².
- **37 das 50** regras Apriori mantiveram os critérios em 2025. Com o IBGE, o recall da árvore passou de **53,6% para 64,7%**, com **570 falsos positivos adicionais**. A ROC-AUC da floresta passou de **0,571 para 0,587**, com leve redução do F1.

[Metodologia, cobertura e cruzamentos](docs/etapa02.md) · [Estabilidade do Apriori](resultados/etapa03/estabilidade_apriori.csv) · [Métricas e matrizes](resultados/etapa03/metricas_temporais.csv) · [Diferenças com IBGE e intervalos](resultados/etapa03/ganhos_ibge_2025.csv)

## Estrutura

| Diretório | Conteúdo |
| --- | --- |
| `work/` | Três ZIPs da PRF, implementação original do Apriori e referência congelada para reconciliação e teste. |
| `dados/externos/ibge/` | Arquivos oficiais do IBGE e manifesto com URLs e SHA-256. |
| `dados/referencias/` e `dados/processados/` | Equivalências de nomes, base integrada, dimensão municipal e política de preditores. |
| `src/proex/` e `scripts/` | Preparação, integração, análise exploratória, classificação e comandos de reprodução. |
| `resultados/etapa02/` e `resultados/etapa03/` | Cruzamentos, gráficos, registros técnicos de integridade e resultados experimentais. |
| `outputs/dashboard_prf/` | Interface Streamlit, tema e atalhos de execução. |
| `tests/` e `docs/` | Testes automatizados e documentação técnica. |

## Instalação, dashboard e testes

Na raiz do repositório, com Python 3.12:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-etapa02.txt -r outputs/dashboard_prf/requirements.txt
python -m pytest -q
bash outputs/dashboard_prf/iniciar.sh
```

Abra [localhost:8501](http://localhost:8501). O dashboard reutiliza a base, os gráficos e as previsões versionadas. No Windows, ative o ambiente com `.venv\Scripts\activate` e use `outputs\dashboard_prf\iniciar.bat`. Se a porta estiver ocupada, defina `PROEX_DASHBOARD_PORT` e use a porta indicada no terminal.

## Reprodução

Após a instalação das dependências, os arquivos oficiais incluídos permitem executar as etapas offline. O primeiro comando recria a preparação, a integração e os cruzamentos. O segundo recalcula os classificadores e a estabilidade das regras.

```bash
python -m scripts.etapa02 executar
python -m scripts.etapa03
```

Para executar a Etapa 02 em partes, use `preparar`, `integrar` e `explorar`, nessa ordem. O subcomando `coletar` verifica os arquivos locais do IBGE e usa `curl` para baixar fontes oficiais ausentes. A recriação dos resultados também gera os diagnósticos detalhados de auditoria na cópia local.

## Fontes oficiais

- **PRF.** Acidentes de 2023, 2024 e 2025 agrupados por ocorrência. Os ZIPs preservam as versões analisadas. [Dados Abertos da PRF](https://www.gov.br/prf/pt-br/acesso-a-informacao/dados-abertos/dados-abertos-da-prf) · [Dicionário das ocorrências](https://www.gov.br/prf/pt-br/acesso-a-informacao/dados-abertos/dicionario-acidentes) · [Proveniência e SHA-256](resultados/etapa02/auditoria/prf.json)
- **IBGE.** API de Localidades, SIDRA 4714, 9923 e 6579 e Malha Municipal Digital do Paraná de 2022. Estimativas anuais estão disponíveis no recorte para 2024 e 2025. Os créditos, links e hashes constam do manifesto. [Dados Abertos do IBGE](https://www.ibge.gov.br/acesso-informacao/dados-abertos.html) · [Malha Municipal de 2022](https://www.ibge.gov.br/geociencias/organizacao-do-territorio/malhas-territoriais/15774-malhas.html?edicao=36516) · [Manifesto de coleta](dados/externos/ibge/manifesto.json)
