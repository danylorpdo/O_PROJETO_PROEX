# Etapa 02 · Integração PRF e IBGE

Danylo Oliveira · Engenharia de Software · FAG

## Fontes e compatibilidade temporal

A fonte primária da PRF são os ZIPs de 2023, 2024 e 2025, agrupados por ocorrência, que já estavam em `work/`. Os hashes e as URLs da versão utilizada constam em [prf.json](../resultados/etapa02/auditoria/prf.json). As definições vêm do [dicionário de acidentes da PRF](https://www.gov.br/prf/pt-br/acesso-a-informacao/dados-abertos/dicionario-acidentes). Os arquivos somam 213.497 registros nacionais. [Portal de Dados Abertos da PRF](https://www.gov.br/prf/pt-br/acesso-a-informacao/dados-abertos/dados-abertos-da-prf)

Foram baixados cinco arquivos do IBGE em 24/11/2026, com horário de Brasília. O [manifesto de coleta](../dados/externos/ibge/manifesto.json) registra a URL exata de cada arquivo, data e hora, período de referência, formato, campos selecionados, tamanho em bytes e SHA-256.

| Fonte | Recorte e variáveis utilizadas |
| --- | --- |
| [API de Localidades](https://servicodados.ibge.gov.br/api/v1/localidades/estados/41/municipios) | Cadastro dos 399 municípios paranaenses na data da coleta. Código de sete dígitos, nome oficial e UF. |
| [SIDRA 4714](https://apisidra.ibge.gov.br/values/t/4714/n6/in%20n3%2041/v/all/p/2022) | Censo 2022. População residente, área territorial em km² e densidade oficial em habitantes por km². |
| [SIDRA 9923](https://apisidra.ibge.gov.br/values/t/9923/n6/in%20n3%2041/v/93/p/2022/c1/all) | Censo 2022. População total, urbana e rural segundo a situação do domicílio nos 399 municípios. Proporção urbana calculada como população urbana dividida pela população total. |
| [SIDRA 6579](https://apisidra.ibge.gov.br/values/t/6579/n6/in%20n3%2041/v/9324/p/2024,2025) | Estimativas de população residente com referência em 1º de julho de 2024 e 1º de julho de 2025 para os 399 municípios. |
| [Malha Municipal Digital do Paraná, 2022](https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2022/UFs/PR/PR_Municipios_2022.zip) | ZIP com Shapefile em SIRGAS 2000, EPSG:4674. Código, UF e geometria municipal para conferência das coordenadas. |

A relação publicada em 2023 para o TCU usa população do Censo 2022 com ajustes territoriais informados até abril de 2023. As 7.110 linhas de 2023 têm contexto de 2022 e deixam `populacao_estimada_ano` vazia. A população estimada de 2024 ou 2025 é associada apenas ao ano de referência correspondente. Essas estimativas podem incorporar mudanças de limites e ficam como contexto adicional. Por exemplo, o IBGE informa alteração entre Guaratuba (PR) e Garuva (SC) nas estimativas de 2025. As faixas exploratórias de população e densidade usam a mesma referência censitária de 2022 nos três anos. [Relação publicada em 2023](https://www.ibge.gov.br/estatisticas/sociais/populacao/37734-relacao-da-populacao-dos-municipios-para-publicacao-no-dou.html), [Notas de 2025 do IBGE](https://agenciadenoticias.ibge.gov.br/media/com_mediaibge/arquivos/8383bdedce5a6d972e60dd32671e533a.pdf)

Os totais municipais da tabela 9923 coincidem com os da 4714 nos 399 municípios. O traço na população rural de Curitiba e Pinhais representa zero segundo a convenção do IBGE. Em ambos, a população urbana já equivale ao total. `uso_solo` descreve o local da ocorrência segundo a PRF (Sim = urbano, Não = rural). A proporção urbana do IBGE descreve os residentes do município segundo a situação do domicílio. [Censo 2022 por situação urbana ou rural](https://www.ibge.gov.br/estatisticas/Sociais/populacao/22827-censo-demografico-2022.html?edicao=41851), [Convenções do IBGE](https://www.ibge.gov.br/explica/producao-agropecuaria/pr)

## Preparação, esquema e uso dos campos

Os ZIPs são lidos em Latin-1 com delimitador ponto e vírgula. As saídas CSV usam UTF-8 com BOM, ponto e vírgula como delimitador e ponto decimal. O identificador é uma cadeia de texto que deve ser importada como texto ao abrir o CSV em planilhas.

| Campos | Representação e validação |
| --- | --- |
| `id`, `ano`, `mes`, `data_inversa`, `horario`, `dia_semana` | ID textual único. Ano e mês inteiros. Data ISO, horário HH:MM:SS e dia da semana conferido contra a data. A PRF registrou `6e+05` em 12/05/2024. O ID foi preservado no formato original e sua representação numérica não colide com as demais no recorte. |
| `uf`, `municipio`, `br`, `km`, `latitude`, `longitude` | Recorte PR, município original, BR inteira, km e coordenadas decimais. Os 31 códigos originais BR igual a zero ficam na base e são tratados como rodovia ausente nas análises. Km igual a zero foi preservado. Todos os valores de latitude/longitude passam pelos limites numéricos e seguem para conferência geográfica. |
| `causa_acidente`, `tipo_acidente`, `fase_dia`, `sentido_via`, `condicao_metereologica`, `tipo_pista`, `tracado_via`, `uso_solo` | Categorias originais. O traçado pode conter vários elementos separados por ponto e vírgula e cada elemento é validado. A causa é texto categórico não vazio. As outras categorias são confrontadas com seus domínios. O nome `condicao_metereologica` conserva a grafia do cabeçalho original. |
| `classificacao_acidente`, `pessoas`, `mortos`, `feridos_leves`, `feridos_graves`, `ilesos`, `ignorados`, `feridos`, `veiculos`, `regional`, `delegacia`, `uop` | Campos de auditoria. Contagens são inteiros não negativos. A classificação original é conferida contra óbitos. |
| `gravidade` | `grave` se mortos > 0 ou feridos graves > 0. Nos demais casos, `nao_grave`. |
| `codigo_ibge`, `municipio_ibge`, `municipio_chave`, `status_vinculo_ibge`, `codigos_candidatos_ibge` | Código textual de sete dígitos, nome oficial, nome normalizado, método de vínculo e candidatos da chave. A barra vertical separa múltiplos códigos. |
| `populacao_2022`, `area_km2_2022`, `densidade_hab_km2_2022`, `populacao_urbana_2022`, `populacao_rural_2022`, `proporcao_urbana_2022` | Contexto censitário fixo. Populações inteiras, área e densidade decimais, proporção entre zero e um. |
| `populacao_estimada_ano`, `status_estimativa` | Estimativa inteira do ano e estado `disponivel`, `ano_sem_estimativa` ou `sem_vinculo_ibge`. |
| `codigos_malha_2022`, `verificacao_geografica` | Códigos dos polígonos que abrangem a coordenada e situação da conferência. O ponto original é sempre preservado. |

A função `extrair_preditores` e a [lista positiva de preditores](../dados/processados/politica_preditores.json) são o ponto de entrada para futuras rotinas de modelagem. A projeção exclui o alvo, a classificação oficial de vítimas, contagens de envolvidos, vítimas e veículos e demais campos registrados para auditoria. Também deixa fora causa e tipo de acidente, cuja disponibilidade depende do momento da previsão, e as estimativas anuais, publicadas após parte dos registros de cada ano. Os campos completos permanecem na base de auditoria.

## Integração e qualidade

1. O vínculo usa `(UF, município normalizado)` com maiúsculas, remoção de diacríticos e pontuação transformada em separadores. Uma tabela [de equivalências](../dados/referencias/aliases_municipais.csv), com justificativa e fonte oficial, cobre as duas grafias da PRF com apóstrofo suprimido.
2. Cada código IBGE tem uma linha na dimensão municipal. As estimativas são únicas por código e ano. O vínculo é uma junção à esquerda, many-to-one, e a sequência de pares ID e gravidade é conferida antes e depois. Uma chave ambígua ou sem correspondência preserva a linha com código e atributos municipais vazios. As coordenadas ficam disponíveis para revisão.
3. A conferência geográfica cruza `(longitude, latitude)` com os polígonos do IBGE, incluindo fronteiras. A PRF publica coordenadas geodésicas decimais. A comparação trata graus geográficos como diretamente comparáveis à malha SIRGAS 2000, sem transformação de datum ou margem de tolerância. O município declarado pela PRF é o critério de vínculo. As divergências ficam como indicadores porque podem refletir imprecisão do ponto, município registrado ou mudanças de limites. A malha é fixa em 2022 para todo o período.

| Recorte | Ocorrências | Graves | Não graves | Municípios vinculados | Vínculo | Com estimativa do ano |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2023 | 7.110 | 1.952 | 5.158 | 147 | 100% | 0% |
| 2024 | 7.583 | 1.966 | 5.617 | 150 | 100% | 100% |
| 2025 | 7.630 | 1.946 | 5.684 | 149 | 100% | 100% |
| Total | 22.323 | 5.864 | 16.459 | 158 | 100% | 68,15% |

A cobertura é 100% também por gravidade. São 22.293 vínculos exatos normalizados e 30 por equivalência documentada. A junção adicionou zero linhas e a proporção de graves ficou em 26,27%. A [auditoria de integração](../resultados/etapa02/auditoria/integracao.json) discrimina anos, classes, municípios e métodos.

Das 22.323 coordenadas, 20.986 (94,01%) coincidiram com o município vinculado pelo nome. Outras 1.290 caíram em outro município da malha e 47 ficaram fora dos polígonos paranaenses de 2022. Entre as equivalências, 23 pontos conferiram. Seis registros declarados em Pérola d'Oeste caíram em Pranchita e o registro declarado em Rancho Alegre D'Oeste caiu em Goioerê. O comando de integração gera a revisão geográfica por ocorrência na cópia local. [Códigos de municípios do IBGE](https://www.ibge.gov.br/explica/codigos-dos-municipios.php)

Além da ausência esperada de estimativa para 2023, a [auditoria de integração](../resultados/etapa02/auditoria/integracao.json) identifica 31 códigos zero de BR, 31 ocorrências com sentido da via não informado e 280 com condição meteorológica ignorada. Todos os campos censitários de 2022 foram preenchidos nas 22.323 ocorrências.

## Cruzamentos e interpretação

Os sete cruzamentos incluem contagens absolutas e denominadores. Em gravidade, a proporção é graves divididos pelo total da célula. Em uso do solo, a proporção é a categoria de uso dividida pelo total da faixa de densidade. As faixas e os critérios ficam em [criterios.json](../resultados/etapa02/tabelas/criterios.json). Grupos com menos de 30 observações permanecem nos CSVs com marcação e sem intervalo. Os demais têm intervalo descritivo de Wilson de 95%. Os intervalos não ajustam a dependência espacial ou temporal nem as múltiplas comparações. Os gráficos por município e rodovia exibem os doze grupos com mais registros, e o gráfico por tipo de acidente mostra os seis tipos mais frequentes.

| Cruzamento | Tabela | Figura |
| --- | --- | --- |
| Município e gravidade | [CSV](../resultados/etapa02/tabelas/municipio_gravidade.csv) | [PNG](../resultados/etapa02/graficos/municipio_gravidade.png) |
| Densidade e gravidade | [CSV](../resultados/etapa02/tabelas/densidade_gravidade.csv) | [PNG](../resultados/etapa02/graficos/densidade_gravidade.png) |
| Faixa populacional e gravidade | [CSV](../resultados/etapa02/tabelas/populacao_gravidade.csv) | [PNG](../resultados/etapa02/graficos/populacao_gravidade.png) |
| Uso do solo e densidade | [CSV](../resultados/etapa02/tabelas/uso_solo_densidade.csv) | [PNG](../resultados/etapa02/graficos/uso_solo_densidade.png) |
| Tipo de pista, fase do dia e gravidade | [CSV](../resultados/etapa02/tabelas/pista_fase_gravidade.csv) | [PNG](../resultados/etapa02/graficos/pista_fase_gravidade.png) |
| Tipo de acidente, densidade municipal e gravidade | [CSV](../resultados/etapa02/tabelas/tipo_acidente_contexto_gravidade.csv) | [PNG](../resultados/etapa02/graficos/tipo_acidente_contexto_gravidade.png) |
| Rodovia, município e gravidade | [CSV](../resultados/etapa02/tabelas/rodovia_municipio_gravidade.csv) | [PNG](../resultados/etapa02/graficos/rodovia_municipio_gravidade.png) |

Nos municípios com menos de 25 hab./km², 32,7% das ocorrências foram graves (1.166/3.565). Na faixa de 500 hab./km² ou mais, foram 20,7% (773/3.730). Restrita a análise às coordenadas que conferem com o município, as proporções foram 33,0% (1.072/3.247) e 20,9% (728/3.476). A ordem das faixas extremas permaneceu a mesma nesse recorte. [Análise de sensibilidade geográfica](../resultados/etapa02/tabelas/sensibilidade_geografica_densidade.csv)

As proporções descrevem a gravidade entre ocorrências registradas pela PRF. População residente caracteriza os municípios, enquanto a exposição ao tráfego exigiria denominadores de circulação, como volume de veículos ou veículos-quilômetro. Os cruzamentos descrevem associações observacionais e não sustentam inferência causal.
