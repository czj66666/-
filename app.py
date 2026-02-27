import streamlit as st
import pulp
import pandas as pd
import plotly.graph_objects as go
from io import BytesIO
import datetime
from openpyxl import Workbook

# ==================== 页面配置 ====================
st.set_page_config(page_title="Blueberry Pro v21.0", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #f1f5f9; border-radius: 10px; border-left: 6px solid #1e3a8a; }
    .stMetric label { color: #1e3a8a !important; font-weight: bold; }
    h1, h2, h3 { color: #1e3a8a; }
    </style>
""", unsafe_allow_html=True)

# ==================== 初始化肥料库 ====================
if 'fert_lib' not in st.session_state:
    init_data = {
        "Urea 尿素": [0,0,0,0,0,0,0,0,0.46],
        "MAP 磷酸一铵": [0,0.12,0.266,0,0,0,0,0,0],
        "MKP 磷酸二氢钾": [0,0,0.227,0.299,0,0,0,0,0],
        "KNO3 硝酸钾": [0.135,0,0,0.38,0,0,0,0,0],
        "K2SO4 硫酸钾": [0,0,0,0.446,0,0,0,0.184,0],
        "Mg(NO3)2 硝酸镁": [0.10,0,0,0,0.09,0,0,0,0],
        "MgSO4 硫酸镁": [0,0,0,0,0.095,0,0,0.125,0],
        "Ca(NO3)2 硝酸钙": [0.11,0,0,0,0,0.16,0,0,0],
        "AmSulphate 硫酸铵": [0,0.21,0,0,0,0,0,0.24,0],
        "Iron 螯合铁": [0,0,0,0,0,0,0.13,0,0]
    }

    st.session_state.fert_lib = pd.DataFrame.from_dict(
        init_data, orient='index',
        columns=["NO3-N","NH4-N","P","K","Mg","Ca","Fe","SO4","Urea-N"]
    )

# ==================== 核心计算 ====================
def safe_calc(inputs, vol, rate, water, ec_factor):

    lib = st.session_state.fert_lib.fillna(0.0).to_dict('index')
    ppm = {col:0.0 for col in st.session_state.fert_lib.columns}

    for name,kg in inputs.items():
        if name in lib and kg > 0:
            factor = (kg * 1000000 * rate) / vol
            for col in ppm.keys():
                ppm[col] += factor * float(lib[name][col])

    res = {
        "NO3-N": ppm["NO3-N"] + water["NO3"],
        "NH4-N": ppm["NH4-N"] + water["NH4"],
        "Urea-N": ppm["Urea-N"],
        "P": ppm["P"] + water["P"],
        "K": ppm["K"] + water["K"],
        "Ca": ppm["Ca"] + water["Ca"],
        "Mg": ppm["Mg"] + water["Mg"],
        "SO4": ppm["SO4"],
        "Fe": ppm["Fe"]
    }

    meq = {
        "NH4+": res["NH4-N"]/14.01,
        "K+": res["K"]/39.1,
        "Ca2+": res["Ca"]/20.04,
        "Mg2+": res["Mg"]/12.15,
        "NO3-": res["NO3-N"]/14.01,
        "H2PO4-": res["P"]/30.97,
        "SO4 2-": res["SO4"]/48.03
    }

    s_cat = sum([meq["NH4+"],meq["K+"],meq["Ca2+"],meq["Mg2+"]])
    s_ani = sum([meq["NO3-"],meq["H2PO4-"],meq["SO4 2-"]])
    total_n = res["NO3-N"] + res["NH4-N"] + res["Urea-N"]

    est_ec = ((s_cat+s_ani)/20) * ec_factor + water["EC"]

    return res,total_n,meq,est_ec,s_cat,s_ani


# ==================== Excel 导出 ====================
def export_to_excel(solution_dict,res,meq,total_n,ec,sc,sa):

    wb = Workbook()

    ws1 = wb.active
    ws1.title = "Fertilizer Plan"
    ws1.append(["肥料名称","投料 kg"])
    for k,v in solution_dict.items():
        ws1.append([k,round(v,4)])

    ws2 = wb.create_sheet("Element PPM")
    ws2.append(["元素","ppm"])
    for k,v in res.items():
        ws2.append([k,round(v,3)])

    ws3 = wb.create_sheet("Ion Balance")
    ws3.append(["离子","meq/L"])
    for k,v in meq.items():
        ws3.append([k,round(v,3)])
    ws3.append([])
    ws3.append(["Σ 阳离子",round(sc,3)])
    ws3.append(["Σ 阴离子",round(sa,3)])
    ws3.append(["电荷差",round(sc-sa,3)])

    ws4 = wb.create_sheet("System Info")
    ws4.append(["总氮",round(total_n,3)])
    ws4.append(["预测 EC",round(ec,3)])
    ws4.append(["生成时间",datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])

    return wb


# ==================== UI ====================
st.title("🧪 蓝莓数字化生产管控终端 v21.0,褚梓健最终版")

tab1,tab2,tab3 = st.tabs(["🏗️ 肥料库","🔎 配方回测","🚀 AI 设计"])

# ----- TAB1 -----
with tab1:
    st.session_state.fert_lib = st.data_editor(
        st.session_state.fert_lib,
        num_rows="dynamic",
        use_container_width=True
    )

# ----- 侧边栏 -----
with st.sidebar:
    st.header("⚙️ 系统参数")
    tank_vol = st.number_input("母液桶体积(L)",value=1000)
    dosing_rate = st.number_input("吸肥比例(%)",value=0.53)/100
    ec_calib = st.slider("EC 修正系数",0.8,1.4,1.08,0.01)

    st.divider()
    st.header("💧 原水数据")

    w_data = {
        "NO3": st.number_input("NO3-N",0.0),
        "NH4": st.number_input("NH4-N",0.0),
        "P": st.number_input("P",0.0),
        "K": st.number_input("K",0.0),
        "Ca": st.number_input("Ca",0.0),
        "Mg": st.number_input("Mg",0.0),
        "EC": st.number_input("原水 EC",0.05)
    }


# ==================== 结果展示 ====================
def show_results(res,tn,meq,ec,sc,sa,final_dict):

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("总氮",f"{round(tn,1)} ppm")
    c2.metric("预测 EC",f"{round(ec,2)}")
    c3.metric("Σ 阳",round(sc,2))
    c4.metric("Σ 阴",round(sa,2))
    c5.metric("电荷差",round(sc-sa,2))

    st.divider()

    l,r = st.columns([1,1.2])

    with l:
        df_res = pd.DataFrame(res.items(),columns=["元素","ppm"])
        st.dataframe(df_res,use_container_width=True)

    with r:
        fig = go.Figure(data=[
            go.Bar(name='阳离子',x=['NH4+','K+','Ca2+','Mg2+'],
                   y=[meq['NH4+'],meq['K+'],meq['Ca2+'],meq['Mg2+']]),
            go.Bar(name='阴离子',x=['NO3-','H2PO4-','SO4 2-'],
                   y=[meq['NO3-'],meq['H2PO4-'],meq['SO4 2-']])
        ])
        fig.update_layout(height=350,barmode='group')
        st.plotly_chart(fig,use_container_width=True)

    wb = export_to_excel(final_dict,res,meq,tn,ec,sc,sa)
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"Blueberry_Report_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

    st.download_button(
        "📥 下载完整Excel报告",
        buffer,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ==================== TAB2 回测 ====================
with tab2:

    names = st.session_state.fert_lib.index.tolist()
    inputs = {}
    cols = st.columns(3)

    for i,n in enumerate(names):
        with cols[i%3]:
            inputs[n] = st.number_input(f"{n}(kg)",0.0,step=0.1)

    if st.button("开始分析"):
        r,t,m,e,sc,sa = safe_calc(inputs,tank_vol,dosing_rate,w_data,ec_calib)
        show_results(r,t,m,e,sc,sa,inputs)


# ==================== TAB3 AI设计 ====================
with tab3:

    d1,d2,d3 = st.columns(3)
    tg = {
        "NO3-N": d1.number_input("目标 NO3-N",0.0,300.0,100.0),
        "NH4-N": d1.number_input("目标 NH4-N",0.0,300.0,50.0),
        "P": d2.number_input("目标 P",0.0,100.0,40.0),
        "K": d2.number_input("目标 K",0.0,400.0,180.0),
        "Ca": d3.number_input("目标 Ca",0.0,200.0,80.0),
        "Mg": d3.number_input("目标 Mg",0.0,100.0,30.0)
    }

    if st.button("🚀 求解最优投料"):
        prob = pulp.LpProblem("Opt",pulp.LpMinimize)
        names = st.session_state.fert_lib.index.tolist()
        v = {n:pulp.LpVariable(f"id_{i}",0,100) for i,n in enumerate(names)}

        prob += pulp.lpSum([v[n] for n in names])

        cf = (1000000*dosing_rate)/tank_vol
        lib = st.session_state.fert_lib.fillna(0.0).to_dict('index')

        def get_p(col):
            return pulp.lpSum([v[n]*cf*float(lib[n][col]) for n in names])

        prob += get_p("NO3-N") == tg["NO3-N"] - w_data["NO3"]
        prob += get_p("NH4-N") == tg["NH4-N"] - w_data["NH4"]
        prob += get_p("P") == tg["P"] - w_data["P"]
        prob += get_p("K") == tg["K"] - w_data["K"]
        prob += get_p("Ca") == tg["Ca"] - w_data["Ca"]
        prob += get_p("Mg") == tg["Mg"] - w_data["Mg"]

        prob.solve(pulp.PULP_CBC_CMD(msg=False))

        if pulp.LpStatus[prob.status]=='Optimal':
            sol = {n:pulp.value(v[n]) for n in names if pulp.value(v[n])>0.001}
            st.success("✅ 找到最优方案")
            st.table(pd.DataFrame(sol.items(),columns=["肥料","kg"]))
            r,t,m,e,sc,sa = safe_calc(sol,tank_vol,dosing_rate,w_data,ec_calib)
            show_results(r,t,m,e,sc,sa,sol)
        else:
            st.error("❌ 无法满足目标，请检查目标比例")

st.caption("Blueberry Pro v21.0 | 2026 工业级版本")