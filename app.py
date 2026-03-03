import streamlit as st
import pulp
import pandas as pd
import plotly.graph_objects as go
from io import BytesIO
import datetime
from openpyxl import Workbook

# ==================== 页面配置 ====================
st.set_page_config(page_title="Blueberry Pro v1.2", layout="wide")

st.markdown("""
<style>
[data-testid="stMetricValue"] { color: black !important; }
[data-testid="stMetricLabel"] { color: #1e3a8a !important; font-weight: bold; }
.stMetric { background-color: #f1f5f9; border-radius: 10px; border-left: 6px solid #1e3a8a; }
h1, h2, h3 { color: #1e3a8a; }
</style>
""", unsafe_allow_html=True)

# ==================== 初始化肥料库 ====================
if 'fert_lib' not in st.session_state:
    cols = ["NO3-N","NH4-N","P","K","Mg","Ca","Fe","SO4-S","Mn","Zn","Cu","B","Mo","Urea-N"]
    init_data = {
        "Urea 尿素": [0,0,0,0,0,0,0,0,0,0,0,0,0,0.46],
        "MAP 磷酸一铵": [0,0.12,0.266,0,0,0,0,0,0,0,0,0,0,0],
        "MKP 磷酸二氢钾": [0,0,0.227,0.299,0,0,0,0,0,0,0,0,0,0],
        "KNO3 硝酸钾": [0.135,0,0,0.38,0,0,0,0,0,0,0,0,0,0],
        "K2SO4 硫酸钾": [0,0,0,0.446,0,0,0,0.18,0,0,0,0,0,0],
        "Mg(NO3)2 硝酸镁": [0.10,0,0,0,0.09,0,0,0,0,0,0,0,0,0],
        "MgSO4 硫酸镁": [0,0,0,0,0.095,0,0,0.125,0,0,0,0,0,0],
        "Ca(NO3)2 硝酸钙": [0.11,0,0,0,0,0.16,0,0,0,0,0,0,0,0],
        "AmSulphate 硫酸铵": [0,0.21,0,0,0,0,0,0.24,0,0,0,0,0,0],
        "Iron 螯合铁": [0,0,0,0,0,0,0.13,0,0,0,0,0,0,0],
        "MnSO4 硫酸锰": [0,0,0,0,0,0,0,0.18,0.31,0,0,0,0,0],
        "ZnSO4 硫酸锌": [0,0,0,0,0,0,0,0.17,0,0.35,0,0,0,0],
        "Borax 硼砂": [0,0,0,0,0,0,0,0,0,0,0,0.11,0,0],
        "Mo  钼酸铵": [0,0,0,0,0,0,0,0,0,0,0,0,0.42,0],

        # ✅ 新增：铜来源（否则 Cu 永远只能为 0）
        # CuSO4·5H2O: Cu≈0.255；SO4-S(以S计)≈0.128
        "CuSO4·5H2O 硫酸铜": [0,0,0,0,0,0,0,0.128,0,0,0.255,0,0,0],
    }
    st.session_state.fert_lib = pd.DataFrame.from_dict(init_data, orient='index', columns=cols).fillna(0.0)

# ==================== 核心函数（完全不动） ====================
def safe_calc(inputs, vol, rate, water, ec_factor):
    lib = st.session_state.fert_lib.fillna(0.0).to_dict('index')
    all_cols = st.session_state.fert_lib.columns.tolist()
    ppm = {col:0.0 for col in all_cols}
    for name,kg in inputs.items():
        if name in lib and kg > 0:
            factor = (kg * 1000000 * rate) / vol
            for col in ppm.keys():
                ppm[col] += factor * float(lib[name][col])
    res = {col: ppm[col] + water.get(col, 0.0) for col in all_cols if col != "Urea-N"}
    res["Urea-N"] = ppm["Urea-N"]
    meq = {
        "NH4+": res["NH4-N"]/14.01, "K+": res["K"]/39.1, "Ca2+": res["Ca"]/20.04,
        "Mg2+": res["Mg"]/12.15, "NO3-": res["NO3-N"]/14.01, "H2PO4-": res["P"]/30.97,
        "SO4 2-": res["SO4-S"]/16.03, "HCO3-": water.get("HCO3", 0.0)/61.02
    }
    s_cat = sum([meq["NH4+"],meq["K+"],meq["Ca2+"],meq["Mg2+"]])
    s_ani = sum([meq["NO3-"],meq["H2PO4-"],meq["SO4 2-"],meq["HCO3-"]])
    total_n = res["NO3-N"] + res["NH4-N"] + res["Urea-N"]
    est_ec = ((s_cat+s_ani)/20) * ec_factor + water["EC"]
    return res,total_n,meq,est_ec,s_cat,s_ani

def export_to_excel(solution_dict,res,meq,total_n,ec,sc,sa):
    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Fertilizer Plan"
    ws1.append(["肥料名称","投料 kg"])
    for k,v in solution_dict.items(): ws1.append([k,round(v,4)])
    ws2 = wb.create_sheet("Element PPM")
    ws2.append(["元素","ppm"])
    for k,v in res.items(): ws2.append([k,round(v,3)])
    ws3 = wb.create_sheet("Ion Balance")
    ws3.append(["离子","meq/L"])
    for k,v in meq.items(): ws3.append([k,round(v,3)])
    ws3.append([]); ws3.append(["Σ 阳离子",round(sc,3)]); ws3.append(["Σ 阴离子",round(sa,3)])
    return wb

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
        st.dataframe(df_res,use_container_width=True, hide_index=True)
    with r:
        fig = go.Figure(data=[
            go.Bar(name='阳离子',x=['NH4+','K+','Ca2+','Mg2+'], y=[meq['NH4+'],meq['K+'],meq['Ca2+'],meq['Mg2+']]),
            go.Bar(name='阴离子',x=['NO3-','H2PO4-','SO4 2-','HCO3-'], y=[meq['NO3-'],meq['H2PO4-'],meq['SO4 2-'],meq['HCO3-']])
        ])
        fig.update_layout(height=350,barmode='group')
        st.plotly_chart(fig,use_container_width=True)
    wb = export_to_excel(final_dict,res,meq,tn,ec,sc,sa)
    buffer = BytesIO(); wb.save(buffer); buffer.seek(0)
    st.download_button("📥 下载完整Excel报告", buffer, file_name=f"Blueberry_Report_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ==================== 调酸统一计算 ====================
def get_water_for_calc(w_data, dosing_rate, tank_vol):
    acid_mode = st.session_state.get("acid_mode", "不调酸")
    target_pH = st.session_state.get("target_pH", 5.5)
    acid_type = st.session_state.get("acid_type", "85% 磷酸 (H3PO4)")

    hco3_val = w_data.get("HCO3", 0.0)
    current_hco3_meq = hco3_val / 61.02

    if target_pH <= 5.0:
        target_residual_meq = 0.1
    elif target_pH <= 5.5:
        target_residual_meq = 0.1 + (target_pH - 5.0) * (0.4 / 0.5)
    elif target_pH <= 6.0:
        target_residual_meq = 0.5 + (target_pH - 5.5) * (0.5 / 0.5)
    else:
        target_residual_meq = 1.0

    acid_map = {
        "85% 磷酸 (H3PO4)": {"d": 1.685, "mw": 98.0, "p": 0.85, "val": 1, "el": "P", "el_w": 30.97},
        "98% 硫酸 (H2SO4)": {"d": 1.84, "mw": 98.07, "p": 0.98, "val": 2, "el": "SO4-S", "el_w": 32.06},
        "68% 硝酸 (HNO3)": {"d": 1.41, "mw": 63.01, "p": 0.68, "val": 1, "el": "NO3-N", "el_w": 14.01}
    }
    a = acid_map[acid_type]

    w_data_calc = dict(w_data)
    needed_meq = 0.0
    ml_per_m3 = 0.0
    nutrient_ppm = 0.0
    acid_L_per_bucket = 0.0

    if acid_mode == "调酸":
        needed_meq = max(0.0, current_hco3_meq - target_residual_meq)
        ml_per_m3 = (needed_meq * a["mw"]) / (a["d"] * a["p"] * a["val"])
        nutrient_ppm = (needed_meq / a["val"]) * a["el_w"]
        w_data_calc["HCO3"] = target_residual_meq * 61.02
        w_data_calc[a["el"]] = w_data_calc.get(a["el"], 0.0) + nutrient_ppm
        acid_L_per_bucket = ml_per_m3 * tank_vol / (dosing_rate * 1_000_000)

    return w_data_calc, current_hco3_meq, needed_meq, ml_per_m3, nutrient_ppm, a, target_residual_meq, acid_L_per_bucket

# ==================== 侧边栏（系统参数 + 原水数据） ====================
with st.sidebar:
    st.header("⚙️ 系统参数")
    tank_vol = st.number_input("母液桶体积(L)", value=1000)
    dosing_rate = st.number_input("吸肥比例(%)", value=0.53) / 100
    ec_calib = st.slider("EC 修正系数", 0.8, 1.4, 1.08, 0.01)

    st.divider()
    st.header("💧 原水数据")
    w_elements = ["NO3-N","NH4-N","P","K","Ca","Mg","SO4-S","Fe","Mn","Zn","Cu","B","Mo"]
    w_data = {el: st.number_input(el, 0.0) for el in w_elements}
    w_data["HCO3"] = st.number_input("HCO3 (碳酸氢根) ppm", 0.0)
    w_data["EC"] = st.number_input("原水 EC", 0.05)

# ==================== 主界面 Tabs ====================
st.title("🧪 营养液计算系统 v1.2")

tab1, tab_acid, tab2, tab3 = st.tabs([
    "🏗️ 肥料库",
    "💧 调酸设置",
    "🔎 配方回测",
    "🚀 结果回推"
])

# Tab1：肥料库
with tab1:
    st.session_state.fert_lib = st.data_editor(st.session_state.fert_lib, num_rows="dynamic", use_container_width=True)

# Tab：调酸设置（独立页）
with tab_acid:
    st.header("💧 调酸设置")
    acid_mode = st.selectbox("调酸模式", ["不调酸", "调酸"], index=0, key="acid_mode")
    target_pH = st.slider("目标 pH", 4.0, 7.0, 5.5, 0.1, key="target_pH")
    acid_type = st.selectbox(
        "选择使用的酸液",
        ["85% 磷酸 (H3PO4)", "98% 硫酸 (H2SO4)", "68% 硝酸 (HNO3)"],
        key="acid_type"
    )

    w_data_calc_preview, current_hco3_meq, needed_meq, ml_per_m3, nutrient_ppm, a, target_residual_meq, acid_L = get_water_for_calc(w_data, dosing_rate, tank_vol)

    st.info(f"原水碳酸氢根碱度: {round(current_hco3_meq, 2)} meq/L")

    if acid_mode == "调酸":
        c1, c2, c3 = st.columns(3)
        c1.metric("酸液用量", f"{round(ml_per_m3, 1)} ml/m³", help="每立方米最终营养液")
        c2.metric(f"{a['el']} 增加", f"{round(nutrient_ppm, 1)} ppm")
        c3.metric("单桶酸量", f"{round(acid_L, 2)} L", help="母液桶实际添加体积")
    else:
        st.success("✅ 不调酸，无需添加酸液")

    st.caption(f"✅ 当前设置：模式={acid_mode} | 目标pH={target_pH} | 残余碱度={round(target_residual_meq,2)} meq/L | HCO3={round(w_data_calc_preview.get('HCO3',0.0),1)} ppm")
    st.warning("⚠️ 实际调酸受水温和有机质影响，建议先进行小杯滴定实验验证。")

# Tab2：配方回测
with tab2:
    names = st.session_state.fert_lib.index.tolist()
    inputs = {}
    cols = st.columns(3)
    for i, n in enumerate(names):
        with cols[i % 3]:
            inputs[n] = st.number_input(f"{n}(kg)", 0.0, step=0.1, key=f"t2_{n}")

    st.info("💡 调酸参数已在【💧 调酸设置】页统一设置，点击下方按钮即可使用最新参数")

    if st.button("开始分析"):
        w_data_calc, *_ = get_water_for_calc(w_data, dosing_rate, tank_vol)
        r, tn, m, e, sc, sa = safe_calc(inputs, tank_vol, dosing_rate, w_data_calc, ec_calib)
        show_results(r, tn, m, e, sc, sa, inputs)

# Tab3：结果回推
with tab3:
    st.info("💡 提示：即使无法完全匹配，系统也会给出最接近目标的配肥方案。")
    d1,d2,d3,d4 = st.columns(4)
    tg = {
        "NO3-N": d1.number_input("目标 NO3-N",0.0,300.0,100.0),
        "NH4-N": d1.number_input("目标 NH4-N",0.0,300.0,50.0),
        "P": d2.number_input("目标 P",0.0,100.0,40.0),
        "K": d2.number_input("目标 K",0.0,400.0,180.0),
        "Ca": d3.number_input("目标 Ca",0.0,200.0,80.0),
        "Mg": d3.number_input("目标 Mg",0.0,100.0,30.0),
        "SO4-S": d4.number_input("目标 SO4-S",0.0,200.0,0.0),
        "Fe": d4.number_input("目标 Fe",0.000,10.0,0.0),
        "Mn": d1.number_input("目标 Mn",0.000,7.0,0.0),
        "Zn": d2.number_input("目标 Zn",0.000,5.0,0.0),
        "Cu": d3.number_input("目标 Cu",0.000,3.0,0.0),
        "B": d4.number_input("目标 B",0.000,8.0,0.0),
        "Mo": d2.number_input("目标 Mo",0.000,3.0,0.0),
        "Urea-N": d1.number_input("目标 Urea-N",0.00,100.0,0.0)
    }

    # ✅ 微量不出滑块，但强制命中（固定超高权重）
    MICROS = ["Fe","Mn","Zn","Cu","B","Mo"]
    MICRO_FIXED_WEIGHT = 5000.0
    SO4_RELAX_WEIGHT = 0.2  # 为了让 Mn/Zn/Cu 能命中，SO4 允许更大偏差

    if st.button("🚀 求解最优投料"):
        prob = pulp.LpProblem("Opt", pulp.LpMinimize)
        names = st.session_state.fert_lib.index.tolist()
        v = {n: pulp.LpVariable(f"id_{i}", 0, 100) for i, n in enumerate(names)}
        slacks = {el: pulp.LpVariable(f"s_{el}", 0) for el in tg.keys()}
        cf = (1000000 * dosing_rate) / tank_vol
        lib = st.session_state.fert_lib.fillna(0.0).to_dict('index')

        water_for_calc, *_ = get_water_for_calc(w_data, dosing_rate, tank_vol)

        penalty = 0
        for el, target_val in tg.items():
            actual = pulp.lpSum([v[n]*cf*float(lib[n][el]) for n in names])
            net_target = max(0, target_val - water_for_calc.get(el, 0))
            prob += actual - net_target <= slacks[el]
            prob += net_target - actual <= slacks[el]

            if el in MICROS:
                penalty += slacks[el] * MICRO_FIXED_WEIGHT
            elif el == "SO4-S":
                penalty += slacks[el] * SO4_RELAX_WEIGHT
            else:
                w = 100 if el in ["NO3-N","NH4-N","P","K","Ca","Mg"] else 1
                penalty += slacks[el] * w

        prob += pulp.lpSum([v[n] for n in names]) * 0.01 + penalty
        prob.solve(pulp.PULP_CBC_CMD(msg=False))

        if pulp.LpStatus[prob.status] != 'Infeasible':
            sol = {n: pulp.value(v[n]) for n in names if pulp.value(v[n]) > 0.001}
            st.success("✅ 已生成最接近目标的优化方案")

            sol_df = pd.DataFrame(list(sol.items()), columns=["肥料", "投料 kg"])
            sol_df["投料 kg"] = sol_df["投料 kg"].round(4)
            st.dataframe(sol_df, use_container_width=True, hide_index=True)

            r,tn,m,e,sc,sa = safe_calc(sol,tank_vol,dosing_rate,water_for_calc,ec_calib)
            show_results(r,tn,m,e,sc,sa,sol)

            st.divider()
            st.subheader("📊 各元素目标 vs 实际对比（总浓度）")
            comparison_data = []
            for el, target in tg.items():
                actual_val = r.get(el, 0.0)
                diff = actual_val - target
                pct_error = (diff / target * 100) if target > 0 else 0.0
                comparison_data.append({
                    "元素": el, "目标 ppm": round(target, 2),
                    "实际 ppm": round(actual_val, 2), "差值": round(diff, 2),
                    "%偏差": f"{round(pct_error, 1)}%"
                })
            comp_df = pd.DataFrame(comparison_data)

            def color_deviation(val):
                try:
                    vv = float(str(val).strip('%'))
                    if abs(vv) <= 2:   return 'background-color: #d4edda; color: #155724'
                    elif abs(vv) <= 5: return 'background-color: #fff3cd; color: #856404'
                    else:              return 'background-color: #f8d7da; color: #721c24'
                except: return ''
            styled_df = comp_df.style.applymap(color_deviation, subset=['%偏差']).format({"%偏差": "{}"}).set_properties(**{'text-align': 'center'})
            st.dataframe(styled_df, use_container_width=True, hide_index=True)

            st.caption("✅ 微量元素固定强制命中；为避免硫酸根耦合导致微量被放弃，SO4-S 已做“放松惩罚”。")
        else:
            st.error("❌ 无解：目标/肥料库耦合导致不可同时满足。建议降低 SO4-S 目标或增加更多非硫酸盐的微量来源。")

st.caption("百瑞Blueberry Pro v1.o | 2026")






