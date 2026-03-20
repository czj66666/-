# ==================== 单页面界面 ====================
st.title("🧪 营养液计算系统")
st.caption("单页面简洁版：原水、调酸、肥料库、配方回测、结果回推全部集中显示。")

# ==================== 基础参数 ====================
st.markdown('<div class="simple-box">', unsafe_allow_html=True)
st.subheader("① 基础参数")

c1, c2, c3 = st.columns(3)
with c1:
    tank_vol = st.number_input("母液桶体积(L)", min_value=1.0, value=1000.0, step=100.0)
with c2:
    dosing_rate = st.number_input("吸肥比例(%)", min_value=0.01, value=0.53, step=0.01) / 100
with c3:
    ec_calib = st.slider("EC 修正系数", 0.8, 1.4, 1.08, 0.01)

st.markdown('</div>', unsafe_allow_html=True)

# ==================== 原水数据 ====================
st.markdown('<div class="simple-box">', unsafe_allow_html=True)
st.subheader("② 原水数据")

w_elements = ["NO3-N","NH4-N","P","K","Ca","Mg","SO4-S","Fe","Mn","Zn","Cu","B","Mo"]
w_cols = st.columns(4)
w_data = {}

for i, el in enumerate(w_elements):
    with w_cols[i % 4]:
        w_data[el] = st.number_input(el, min_value=0.0, value=0.0, step=0.1, key=f"w_{el}")

c1, c2, c3 = st.columns(3)
with c1:
    w_data["HCO3"] = st.number_input("HCO3 (碳酸氢根) ppm", min_value=0.0, value=0.0, step=1.0)
with c2:
    w_data["EC"] = st.number_input("原水 EC", min_value=0.0, value=0.05, step=0.01)
with c3:
    w_data["pH"] = st.number_input("原水 pH", min_value=0.0, max_value=14.0, value=7.0, step=0.1)

st.markdown('</div>', unsafe_allow_html=True)

# ==================== 调酸设置 ====================
st.markdown('<div class="simple-box">', unsafe_allow_html=True)
st.subheader("③ 调酸设置")

acid_mode = st.selectbox("调酸模式", ["不调酸", "调酸"], index=0, key="acid_mode")
target_pH = st.slider("目标 pH", 4.0, 7.0, 5.5, 0.1, key="target_pH")

acid_options_map = {
    "磷酸 (H3PO4)": ["75%", "80%", "85%"],
    "硫酸 (H2SO4)": ["50%", "98%"],
    "硝酸 (HNO3)": ["30%", "40%", "55%", "68%"]
}

if "acid_list" not in st.session_state:
    st.session_state.acid_list = [
        {"acid_type": "磷酸 (H3PO4)", "conc_label": "85%", "share": 100.0, "enabled": True}
    ]

if acid_mode == "调酸":
    st.markdown("**酸液组合**")

    if st.button("添加一种酸"):
        st.session_state.acid_list.append({
            "acid_type": "磷酸 (H3PO4)",
            "conc_label": "85%",
            "share": 0.0,
            "enabled": True
        })

    delete_idx = None
    for i, acid in enumerate(st.session_state.acid_list):
        c1, c2, c3, c4, c5 = st.columns([2.2, 1.4, 1.2, 1.0, 0.8])

        acid_types = list(acid_options_map.keys())
        current_type = acid.get("acid_type", "磷酸 (H3PO4)")
        if current_type not in acid_types:
            current_type = "磷酸 (H3PO4)"

        acid["acid_type"] = c1.selectbox(
            f"酸种_{i}",
            acid_types,
            index=acid_types.index(current_type),
            key=f"acid_type_{i}"
        )

        valid_concs = acid_options_map[acid["acid_type"]]
        current_conc = acid.get("conc_label", valid_concs[0])
        if current_conc not in valid_concs:
            current_conc = valid_concs[0]

        acid["conc_label"] = c2.selectbox(
            f"浓度_{i}",
            valid_concs,
            index=valid_concs.index(current_conc),
            key=f"acid_conc_{i}"
        )

        acid["share"] = c3.number_input(
            f"比例%_{i}",
            min_value=0.0,
            max_value=100.0,
            value=float(acid.get("share", 0.0)),
            step=1.0,
            key=f"acid_share_{i}"
        )

        acid["enabled"] = c4.checkbox(
            f"启用_{i}",
            value=acid.get("enabled", True),
            key=f"acid_enable_{i}"
        )

        if c5.button("删除", key=f"acid_del_{i}"):
            delete_idx = i

    if delete_idx is not None:
        st.session_state.acid_list.pop(delete_idx)
        st.rerun()

(
    w_data_calc_preview,
    base_water_preview,
    acid_additions_preview,
    current_hco3_meq,
    needed_meq_total,
    target_residual_meq,
    acid_L_total,
    acid_detail_rows_preview
) = get_water_for_calc(w_data, dosing_rate, tank_vol)

c1, c2, c3, c4 = st.columns(4)
c1.metric("原水 pH", round(w_data.get("pH", 0.0), 2))
c2.metric("碳酸氢根碱度", f"{round(current_hco3_meq, 2)} meq/L")
c3.metric("调酸后 HCO3", f"{round(w_data_calc_preview.get('HCO3', 0.0), 1)} ppm")
c4.metric("总单桶加酸量", f"{round(acid_L_total, 3)} L")

if acid_mode == "调酸" and acid_detail_rows_preview:
    st.dataframe(pd.DataFrame(acid_detail_rows_preview), use_container_width=True, hide_index=True)

raw_ph = w_data.get("pH", 0.0)
raw_hco3 = w_data.get("HCO3", 0.0)
if raw_ph > 7.5 and raw_hco3 < 50:
    st.warning("原水 pH 偏高但 HCO3 不高，建议复测碱度，或检查是否因曝气/失CO2导致 pH 偏高。")
if raw_ph < 6.5 and raw_hco3 > 150:
    st.warning("原水 pH 偏低但 HCO3 偏高，数据组合异常，建议复检原水。")

st.markdown('</div>', unsafe_allow_html=True)

# ==================== 肥料库 ====================
st.markdown('<div class="simple-box">', unsafe_allow_html=True)
st.subheader("④ 肥料库")
st.caption("直接编辑肥料元素含量和单价。")

st.session_state.fert_lib = st.data_editor(
    st.session_state.fert_lib,
    num_rows="dynamic",
    use_container_width=True
)

c1, c2 = st.columns(2)
with c1:
    st.markdown("**大量肥名单**")
    st.write(MACRO_FERTILIZERS)
with c2:
    st.markdown("**微量肥名单**")
    st.write(MICRO_FERTILIZERS)

st.markdown('</div>', unsafe_allow_html=True)

# ==================== 配方回测 ====================
st.markdown('<div class="simple-box">', unsafe_allow_html=True)
st.subheader("⑤ 配方回测")
st.caption("输入已有投料量，查看结果。")

names = st.session_state.fert_lib.index.tolist()
inputs = {}
cols = st.columns(3)
for i, n in enumerate(names):
    with cols[i % 3]:
        inputs[n] = st.number_input(f"{n}(kg)", min_value=0.0, step=0.1, key=f"t2_{n}")

run_analysis = st.button("开始配方回测", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# ==================== 结果回推 ====================
st.markdown('<div class="simple-box">', unsafe_allow_html=True)
st.subheader("⑥ 结果回推")
st.caption("输入目标值，自动求最优投料。")

d1, d2, d3, d4 = st.columns(4)
tg = {
    "NO3-N": d1.number_input("目标 NO3-N", 0.0, 300.0, 100.0),
    "NH4-N": d1.number_input("目标 NH4-N", 0.0, 300.0, 50.0),
    "P": d2.number_input("目标 P", 0.0, 100.0, 40.0),
    "K": d2.number_input("目标 K", 0.0, 400.0, 180.0),
    "Ca": d3.number_input("目标 Ca", 0.0, 200.0, 80.0),
    "Mg": d3.number_input("目标 Mg", 0.0, 100.0, 30.0),
    "SO4-S": d4.number_input("目标 SO4-S", 0.0, 200.0, 40.0),
    "Fe": d4.number_input("目标 Fe", 0.000, 10.0, 0.0),
    "Mn": d1.number_input("目标 Mn", 0.000, 7.0, 0.0),
    "Zn": d2.number_input("目标 Zn", 0.000, 5.0, 0.0),
    "Cu": d3.number_input("目标 Cu", 0.000, 3.0, 0.0),
    "B": d4.number_input("目标 B", 0.000, 8.0, 0.0),
    "Mo": d2.number_input("目标 Mo", 0.000, 3.0, 0.0),
    "Urea-N": d1.number_input("目标 Urea-N", 0.00, 100.0, 0.0)
}

run_opt = st.button("求解最优投料", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# ==================== 回测结果 ====================
if run_analysis:
    (
        water_for_calc,
        base_water,
        acid_additions,
        _current_hco3_meq,
        _needed_meq_total,
        _target_residual_meq,
        _acid_L_total,
        acid_detail_rows
    ) = get_water_for_calc(w_data, dosing_rate, tank_vol)

    r, tn, m, e, sc, sa = safe_calc(inputs, tank_vol, dosing_rate, water_for_calc, ec_calib)
    show_results(
        r, tn, m, e, sc, sa, inputs,
        base_water=base_water,
        acid_additions=acid_additions,
        acid_rows=acid_detail_rows,
        raw_water=w_data
    )

# ==================== 回推结果 ====================
if run_opt:
    lib = st.session_state.fert_lib.fillna(0.0).to_dict('index')
    cf = (1_000_000 * dosing_rate) / tank_vol

    (
        water_for_calc,
        base_water,
        acid_additions,
        _current_hco3_meq,
        _needed_meq_total,
        _target_residual_meq,
        _acid_L_total,
        acid_detail_rows
    ) = get_water_for_calc(w_data, dosing_rate, tank_vol)

    macro_targets = {
        "NO3-N": tg["NO3-N"],
        "NH4-N": tg["NH4-N"],
        "P": tg["P"],
        "K": tg["K"],
        "Ca": tg["Ca"],
        "Mg": tg["Mg"],
        "SO4-S": tg["SO4-S"],
        "Urea-N": tg["Urea-N"]
    }

    micro_targets = {
        "Fe": tg["Fe"],
        "Mn": tg["Mn"],
        "Zn": tg["Zn"],
        "Cu": tg["Cu"],
        "B": tg["B"],
        "Mo": tg["Mo"]
    }

    macro_status, macro_sol, macro_weights, macro_names = solve_macro_targets(
        macro_targets=macro_targets,
        water_for_calc=water_for_calc,
        lib=lib,
        cf=cf
    )

    if macro_status in ['Infeasible', 'Undefined', 'Unbounded']:
        st.error("❌ 大量元素无解，请调整目标值、酸方案或肥料库。")
    else:
        micro_status, micro_sol, micro_names = solve_micro_targets(
            micro_targets=micro_targets,
            lib=lib,
            cf=cf
        )

        final_sol = dict(macro_sol)
        for k, v in micro_sol.items():
            final_sol[k] = final_sol.get(k, 0.0) + v

        st.success("✅ 已完成：大量元素与微量元素分阶段求解")

        c1, c2, c3 = st.columns(3)
        c1.metric("大量阶段允许肥料数", len(macro_names))
        c2.metric("微量阶段允许肥料数", len(micro_names))
        c3.metric("最终投料肥料数", len(final_sol))

        if macro_sol:
            st.subheader("大量元素方案")
            macro_df = pd.DataFrame({
                "肥料": list(macro_sol.keys()),
                "投料量": [format_weight(v) for v in macro_sol.values()]
            })
            st.dataframe(macro_df, use_container_width=True, hide_index=True)

        if micro_sol:
            st.subheader("微量元素方案")
            micro_df = pd.DataFrame({
                "肥料": list(micro_sol.keys()),
                "投料量": [format_weight(v) for v in micro_sol.values()]
            })
            st.dataframe(micro_df, use_container_width=True, hide_index=True)
        else:
            if micro_status in ['Infeasible', 'Undefined', 'Unbounded']:
                st.warning("⚠️ 微量元素直接求解无解。")
            else:
                st.info("本次微量元素无需额外补充。")

        r, tn, m, e, sc, sa = safe_calc(final_sol, tank_vol, dosing_rate, water_for_calc, ec_calib)
        show_results(
            r, tn, m, e, sc, sa, final_sol,
            base_water=base_water,
            acid_additions=acid_additions,
            acid_rows=acid_detail_rows,
            raw_water=w_data
        )

        st.subheader("大量元素目标 vs 实际对比")
        comparison_data = []
        for el, target in macro_targets.items():
            actual_val = r.get(el, 0.0)
            diff = actual_val - target
            pct_error = (diff / target * 100) if target > 0 else 0.0
            comparison_data.append({
                "元素": el,
                "目标 ppm": round(target, 4),
                "实际 ppm": round(actual_val, 4),
                "差值": round(diff, 4),
                "%偏差": f"{round(pct_error, 1)}%"
            })
        comp_df = pd.DataFrame(comparison_data)
        st.dataframe(comp_df, use_container_width=True, hide_index=True)

        st.subheader("微量元素目标 vs 实际对比")
        micro_compare = []
        for el, target in micro_targets.items():
            actual_val = r.get(el, 0.0)
            diff = actual_val - target
            pct_error = (diff / target * 100) if target > 0 else 0.0
            micro_compare.append({
                "元素": el,
                "目标 ppm": round(target, 4),
                "最终实际 ppm": round(actual_val, 4),
                "差值": round(diff, 4),
                "%偏差": f"{round(pct_error, 1)}%"
            })
        micro_df = pd.DataFrame(micro_compare)
        st.dataframe(micro_df, use_container_width=True, hide_index=True)

st.caption("百瑞果蔬 Blueberry v1.1")
