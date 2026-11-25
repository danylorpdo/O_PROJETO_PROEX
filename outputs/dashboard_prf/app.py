"""Dashboard acadêmico da análise PRF e IBGE."""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
ETAPA02 = ROOT / "resultados" / "etapa02"
ETAPA03 = ROOT / "resultados" / "etapa03"
BASE = ROOT / "dados" / "processados" / "prf_ibge_integrada.csv"

st.set_page_config(page_title='PRF Paraná · Mineração de dados', page_icon='📊', layout='wide')
st.markdown('''<style>
.block-container {padding-top:4.5rem; max-width:1440px;}
h1 {letter-spacing:-1.4px; font-weight:750 !important;}
[data-testid="stMetricValue"] {color:#126b65;}
[data-testid="stSidebar"] {border-right:1px solid #dce4e8;}
.intro {color:#546570;font-size:1.08rem;max-width:920px;margin-bottom:1.8rem;}
.eyebrow {color:#126b65;letter-spacing:2px;font-weight:700;font-size:.78rem;}
</style>''', unsafe_allow_html=True)

@st.cache_data
def ler_csv(caminho, versao):
    return pd.read_csv(caminho, sep=";", encoding="utf-8-sig", dtype={"id": str, "codigo_ibge": str})


def tabela(caminho):
    return ler_csv(caminho, caminho.stat().st_mtime_ns)


def ler_json(caminho):
    return json.loads(caminho.read_text(encoding="utf-8"))


def numero(x):
    return f"{int(x):,}".replace(",", ".")


def pct(x):
    return f"{x:.2%}".replace(".", ",")


def csv_bytes(df):
    return df.to_csv(index=False, sep=";").encode("utf-8-sig")


arquivos_necessarios = [
    BASE, ETAPA02 / "auditoria" / "integracao.json", ETAPA02 / "auditoria" / "prf.json",
    ETAPA02 / "graficos" / "populacao_gravidade.png", ETAPA02 / "graficos" / "densidade_gravidade.png",
    *(ETAPA03 / nome for nome in ("classificacao.json", "apriori.json", "estabilidade_apriori.csv",
                                  "metricas_temporais.csv", "previsoes_2025.csv")),
]
if faltantes := [str(caminho.relative_to(ROOT)) for caminho in arquivos_necessarios if not caminho.is_file()]:
    st.error("Arquivos ausentes. Execute os comandos de reprodução do README na raiz do projeto.")
    st.code("\n".join(faltantes))
    st.stop()

base = tabela(BASE).assign(grave=lambda dados: dados.gravidade.eq("grave"))
resultado = ler_json(ETAPA03 / "classificacao.json")
integracao = ler_json(ETAPA02 / "auditoria" / "integracao.json")
if resultado["sha256_base_integrada"] != integracao["sha256_base_integrada"]:
    st.error("A base integrada e os resultados pertencem a versões diferentes. Execute a Etapa 03.")
    st.stop()

with st.sidebar:
    st.markdown("### PRF / Paraná")
    st.caption("PROJETO DE MINERAÇÃO DE DADOS")
    anos = st.multiselect("Anos na visão geral", [2023, 2024, 2025], default=[2023, 2024, 2025])
    municipios = st.multiselect("Municípios", sorted(base.municipio_ibge.dropna().unique()),
                                placeholder="Todos os municípios")
    st.caption("Os filtros atualizam os indicadores, os gráficos interativos e a base para download.")
    st.divider()
    st.markdown("**O que é um acidente grave?**")
    st.write("Uma ocorrência com pelo menos uma pessoa morta ou gravemente ferida.")
    st.divider()
    st.markdown("**Danylo Oliveira**  \nEngenharia de Software · FAG")

st.markdown('<div class="eyebrow">SEGURANÇA VIÁRIA · CLASSIFICAÇÃO SUPERVISIONADA</div>', unsafe_allow_html=True)
st.title("Gravidade dos acidentes no Paraná")
st.markdown(
    '<div class="intro">Explore os acidentes registrados pela PRF, o contexto municipal do IBGE '
    'e o desempenho dos classificadores em 2025.</div>', unsafe_allow_html=True,
)
df = base.loc[base.ano.isin(anos)]
if municipios:
    df = df.loc[df.municipio_ibge.isin(municipios)]
taxa = df.grave.mean()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Acidentes registrados", numero(len(df)))
c2.metric("Ocorrências graves", numero(df.grave.sum()))
c3.metric("Proporção de graves", pct(taxa) if len(df) else "—")
c4.metric("Vínculo municipal IBGE", pct(df.codigo_ibge.notna().mean()) if len(df) else "—")
st.caption("Os indicadores descrevem as ocorrências do recorte selecionado.")
overview, classification, interpretation, method = st.tabs(
    ["Visão geral", "Classificação", "Interpretação", "Base e método"],
)

def estilo(fig):
    fig.update_layout(height=350,margin=dict(l=10,r=25,t=20,b=20),font=dict(family='Arial',color='#263e4c'),
                      paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',showlegend=False)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor='#e5ebee',zeroline=False)
    return fig

with overview:
    if df.empty:
        st.info('Selecione anos e municípios com ocorrências para explorar a base.')
    else:
        left,right=st.columns(2,gap='large')
        with left:
            st.subheader('Acidentes por ano')
            counts=df.groupby('ano',as_index=False).agg(acidentes=('id','size'),graves=('grave','sum'))
            counts['ano']=counts.ano.astype(str)
            fig=px.bar(counts,x='ano',y='acidentes',text='acidentes',color_discrete_sequence=['#147d74'],
                       labels={'ano':'Ano','acidentes':'Ocorrências','graves':'Graves'},hover_data=['graves'])
            fig.update_traces(textposition='outside',cliponaxis=False)
            fig.update_yaxes(range=[0,counts.acidentes.max()*1.2])
            st.plotly_chart(estilo(fig),width='stretch',config={'displayModeBar':False})
        with right:
            st.subheader('Gravidade por tipo de pista')
            group=df.groupby('tipo_pista',as_index=False).agg(acidentes=('id','size'),graves=('grave','sum'))
            group['percentual']=100*group.graves/group.acidentes
            group=group.sort_values('percentual')
            fig=px.bar(group,x='percentual',y='tipo_pista',orientation='h',text=group.percentual.map(lambda x:f'{x:.1f}%'),
                       color_discrete_sequence=['#147d74'],hover_data=['acidentes','graves'],
                       labels={'percentual':'Acidentes graves (%)','tipo_pista':'','acidentes':'Ocorrências','graves':'Graves'})
            fig.update_xaxes(range=[0,max(group.percentual.max()*1.28,40)])
            fig.update_traces(textposition='outside',cliponaxis=False)
            fig.add_vline(x=taxa*100,line_dash='dot',line_color='#c08237')
            st.plotly_chart(estilo(fig),width='stretch',config={'displayModeBar':False})
            st.caption(f'Linha pontilhada: proporção geral de graves no recorte ({pct(taxa)}).')
        st.subheader('Gravidade ao longo do dia')
        g=df.groupby('fase_dia',as_index=False).agg(acidentes=('id','size'),graves=('grave','sum'))
        g['percentual']=100*g.graves/g.acidentes
        fig=px.bar(g,x='fase_dia',y='percentual',text=g.percentual.map(lambda x:f'{x:.1f}%'),
                   category_orders={'fase_dia':['Amanhecer','Pleno dia','Anoitecer','Plena Noite']},
                   color_discrete_sequence=['#426988'],hover_data=['acidentes','graves'],
                   labels={'fase_dia':'','percentual':'Acidentes graves (%)','acidentes':'Ocorrências','graves':'Graves'})
        fig.update_yaxes(range=[0,max(g.percentual.max()*1.3,40)])
        fig.update_traces(textposition='outside',cliponaxis=False)
        st.plotly_chart(estilo(fig),width='stretch',config={'displayModeBar':False})

    st.subheader("Contexto municipal do IBGE")
    if len(df):
        st.caption(f"{numero(df.codigo_ibge.nunique())} municípios vinculados no recorte. "
                   f"{numero(df.populacao_estimada_ano.notna().sum())} ocorrências com estimativa do ano.")
    st.caption("Gráficos históricos para todo o Paraná em 2023–2025, com referência fixa no Censo 2022.")
    tab_densidade, tab_populacao = st.tabs(["Densidade demográfica", "População residente"])
    with tab_densidade:
        st.image(str(ETAPA02 / "graficos" / "densidade_gravidade.png"), width="stretch")
    with tab_populacao:
        st.image(str(ETAPA02 / "graficos" / "populacao_gravidade.png"), width="stretch")
    st.caption("As proporções usam ocorrências da PRF como denominador. Estimar exposição exigiria dados de circulação.")

nomes = resultado["nomes_modelos"]
cenarios = resultado["cenarios"]
metricas = pd.DataFrame(resultado["metricas"])
nomes_metricas = {
    "acuracia": "Acurácia", "precisao": "Precisão", "recall": "Recall", "f1": "F1",
    "roc_auc": "ROC-AUC",
}
formatos = {rotulo: st.column_config.NumberColumn(format="%.3f") for rotulo in nomes_metricas.values()}

with classification:
    st.subheader("Comparação temporal")
    colunas = st.columns(3)
    papeis = {"treino": "Treino", "validacao": "Validação", "teste": "Teste"}
    for coluna, (papel, dados) in zip(colunas, resultado["particoes"].items(), strict=True):
        coluna.metric(f"{papeis[papel]} · {dados['ano']}", numero(dados["ocorrencias"]))
    st.caption("Treino em 2023, validação em 2024 e teste final em 2025. Cada cenário usa as mesmas ocorrências.")
    ano = st.radio("Ano de avaliação", [2025, 2024],
                   format_func={2025: "Teste final · 2025", 2024: "Validação · 2024"}.get, horizontal=True)

    avaliacao = metricas.loc[metricas.ano.eq(ano)]
    comparacao = avaliacao[["modelo", "cenario", *nomes_metricas]].assign(
        modelo=lambda x: x.modelo.map(nomes), cenario=lambda x: x.cenario.map(cenarios),
    ).rename(columns={**nomes_metricas, "modelo": "Modelo", "cenario": "Atributos"})
    comparacao.loc[avaliacao.modelo.eq("majoritaria"), "Atributos"] = "Referência comum"
    st.dataframe(comparacao, hide_index=True, width="stretch", column_config=formatos)
    st.caption("Precisão, recall e F1 referem-se à classe grave. A precisão da referência é zero por convenção.")
    st.download_button("Baixar métricas e matrizes dos dois anos", (ETAPA03 / "metricas_temporais.csv").read_bytes(),
                       "metricas_temporais.csv", "text/csv")

    a, b = st.columns(2)
    modelo = a.selectbox("Modelo para analisar", list(nomes), index=3, format_func=nomes.get)
    opcoes = ["prf"] if modelo == "majoritaria" else list(cenarios)
    cenario = b.selectbox("Atributos na matriz", opcoes, format_func=cenarios.get,
                          key="atributos_matriz")
    caso = avaliacao.loc[avaliacao.modelo.eq(modelo) & avaliacao.cenario.eq(cenario)].iloc[0]
    st.markdown("#### Matriz de confusão")
    rotulos = resultado["rotulos_matrizes"]
    fig = px.imshow([[int(caso.vn), int(caso.fp)], [int(caso.fn), int(caso.vp)]], x=rotulos, y=rotulos,
                    text_auto=True, color_continuous_scale="Teal", aspect="auto",
                    labels={"x": "Classe prevista", "y": "Classe real", "color": "Ocorrências"})
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=20), coloraxis_showscale=False)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.write(f"O modelo identificou **{numero(caso.vp)} de {numero(caso.vp + caso.fn)}** acidentes graves "
             f"e classificou como graves **{numero(caso.fp)}** ocorrências da outra classe.")
    if ano == 2025:
        previsoes = tabela(ETAPA03 / "previsoes_2025.csv")
        with st.expander("Conferir uma ocorrência do teste"):
            posicao = st.number_input("Posição no conjunto de teste", 1, len(previsoes), 1, step=1)
            previsao = previsoes.iloc[posicao - 1]
            linha = base.loc[base.id.eq(previsao.id), ["ano", "id", *resultado["atributos_prf"]]].iloc[0]
            previsto = previsao[f"{modelo}_{cenario}_previsto"]
            st.dataframe(linha.astype(str).rename("Valor").to_frame(), width="stretch")
            st.write(f"Classe real **{rotulos[previsao.real]}** · Classe prevista **{rotulos[previsto]}**")
            st.download_button("Baixar previsões de 2025", (ETAPA03 / "previsoes_2025.csv").read_bytes(),
                               "previsoes_2025.csv", "text/csv")

    with st.expander("Diferenças entre cenários em 2025"):
        ganhos = pd.DataFrame(resultado["ganhos_teste"]).assign(modelo=lambda x: x.modelo.map(nomes))
        colunas = {"modelo": "Modelo", "delta_f1": "Δ F1", "f1_ic95_inferior": "F1 IC95% inf.",
                   "f1_ic95_superior": "F1 IC95% sup.", "delta_roc_auc": "Δ ROC-AUC",
                   "roc_auc_ic95_inferior": "AUC IC95% inf.", "roc_auc_ic95_superior": "AUC IC95% sup."}
        st.dataframe(ganhos[list(colunas)].rename(columns=colunas), hide_index=True, width="stretch",
                     column_config={rotulo: st.column_config.NumberColumn(format="%+.3f")
                                    for campo, rotulo in colunas.items() if campo != "modelo"})
        st.caption("Diferenças PRF + IBGE menos PRF. Intervalos de 95% por reamostragem pareada de municípios.")
    with st.expander("Como ler as métricas"):
        st.markdown("**Acurácia** mede os acertos em toda a amostra. **Precisão** mede a fração de graves entre as "
                    "previsões de grave. **Recall** mede a fração de graves identificados. **F1** equilibra precisão "
                    "e recall. **ROC-AUC** mede a capacidade de ordenar a classe grave acima da outra classe.")

with interpretation:
    st.subheader("Regras de associação")
    resumo = ler_json(ETAPA03 / "apriori.json")
    st.caption(f"{resumo['regras_descobertas']} regras descobertas em 2023–2024. "
               f"{resumo['mantem_criterios_2025']} mantiveram os critérios em 2025.")
    regras = tabela(ETAPA03 / "estabilidade_apriori.csv")
    colunas = {"antecedente": "Condições", "suporte_2023_2024": "Suporte 2023–24",
               "confianca_2023_2024": "Confiança 2023–24", "lift_2023_2024": "Lift 2023–24",
               "suporte_2025": "Suporte 2025", "confianca_2025": "Confiança 2025",
               "lift_2025": "Lift 2025", "mantem_criterios_2025": "Estável"}
    st.dataframe(regras.head(10)[list(colunas)].rename(columns=colunas), hide_index=True, width="stretch",
                 column_config={rotulo: st.column_config.NumberColumn(format="percent" if campo.startswith(
                     ("suporte", "confianca")) else "%.3f") for campo, rotulo in colunas.items()
                                if campo.startswith(("suporte", "confianca", "lift"))})
    st.caption("As dez regras estão ordenadas pelo lift da descoberta. Consequente: acidente grave. "
               "Critérios: suporte ≥ 1%, confiança ≥ 25% e lift > 1.")
    st.download_button("Baixar todas as regras", (ETAPA03 / "estabilidade_apriori.csv").read_bytes(),
                       "estabilidade_apriori.csv", "text/csv")

    st.subheader("Características usadas pelos modelos de árvore")
    a, b = st.columns(2)
    modelo_interpretado = a.selectbox("Modelo para interpretar", ["arvore", "floresta"], format_func=nomes.get)
    cenario_interpretado = b.selectbox("Atributos da interpretação", list(cenarios), format_func=cenarios.get)
    interpretacao = resultado["interpretacoes"][f"{modelo_interpretado}_{cenario_interpretado}"]
    imp = pd.DataFrame(interpretacao["importancias"]).sort_values("importancia")
    fig = px.bar(imp, x="importancia", y="campo", orientation="h", color_discrete_sequence=["#147d74"],
                 labels={"importancia": "Importância", "campo": ""})
    st.plotly_chart(estilo(fig), width="stretch", config={"displayModeBar": False})
    st.caption("Importância interna por redução de impureza. Variáveis contínuas e variáveis com muitas "
               "categorias podem ser favorecidas por essa medida.")
    if "arvore" in interpretacao:
        with st.expander("Regras completas da Árvore de Decisão"):
            st.code(interpretacao["arvore"], language="text")
            st.download_button("Baixar regras da árvore", interpretacao["arvore"], "arvore_decisao.txt", "text/plain")

with method:
    st.subheader("Preparação, treinamento e avaliação")
    st.markdown(
        "1. **Base.** Ocorrências PRF agrupadas por acidente, integradas ao município do IBGE por nome e UF.\n"
        "2. **Alvo.** Pelo menos um óbito ou ferido grave.\n"
        "3. **Atributos.** Dia da semana, fase do dia, clima, pista, uso do solo, rodovia e mês. "
        "O cenário PRF + IBGE inclui população, área, densidade e proporção urbana do Censo 2022.\n"
        "4. **Divisão temporal.** Treino em 2023, validação em 2024 e teste final em 2025. "
        "A codificação e as imputações são ajustadas no treino.\n"
        "5. **Configurações fixas.** Regressão Logística, Árvore de Decisão e Random Forest com pesos de classe "
        "balanceados. A referência sempre escolhe a classe majoritária do treino."
    )
    st.write("As métricas, previsões e regras são calculadas antecipadamente. As estimativas anuais aparecem "
             "como informação da base e os modelos usam a referência censitária fixa.")
    st.caption("O estudo descreve associações entre ocorrências registradas. A conferência com a malha de "
               "2022 aponta diferenças entre coordenada e município declarado em parte dos registros.")
    with st.expander("Conferir e baixar a base do recorte lateral"):
        selecionada = df.drop(columns="grave")
        st.dataframe(selecionada.head(100), hide_index=True, width="stretch")
        st.caption("Amostra de até 100 linhas. O download contém todo o recorte selecionado.")
        st.download_button("Baixar base selecionada", csv_bytes(selecionada), "base_prf_ibge.csv", "text/csv")
    with st.expander("Auditoria dos arquivos originais"):
        for item in ler_json(ETAPA02 / "auditoria" / "prf.json")["anos"]:
            st.markdown(f"**{item['ano']}** · {numero(item['brasil'])} registros no arquivo nacional e "
                        f"{numero(item['analisados'])} no Paraná. [Arquivo original]({item['url']})")
            st.caption(f"SHA-256 · {item['sha256']}")
        st.download_button("Baixar auditoria da integração", (ETAPA02 / "auditoria" / "integracao.json").read_bytes(),
                           "integracao.json", "application/json")
