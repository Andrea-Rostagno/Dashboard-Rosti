    # ── DCF Avanzato (UFCF/FCFF) — replica notebook analisi_universale_v1 ──
    st.markdown("")
    section("🔮","DCF Avanzato — UFCF / FCFF (Mid-Year Convention)")

    # Bank/financial sector detection
    _BANK_KW_S = {"Bank","Insurance","Financial","Thrift","Savings","Credit"}
    _BANK_KW_I = {"Bank","Insurance","Investment","Brokerage","Mortgage","Asset Management"}
    _is_bank_dcf = (any(kw in sector for kw in _BANK_KW_S) or
                    any(kw in industry for kw in _BANK_KW_I))
    if _is_bank_dcf:
        st.warning(f"⚠️ {ticker} è un settore finanziario. Il DCF FCFF NON è applicabile a banche/assicurazioni. Modelli corretti: DDM o P/Book. Risultati puramente indicativi.")

    if price:
        # ── Estrai serie storiche (come Cell 35 notebook) ────────────────
        _rev_s  = df_fund.get("revenue",          pd.Series(dtype=float))
        _ebit_s = df_fund.get("operating_income",  pd.Series(dtype=float))
        _da_s   = df_fund.get("depreciation",      pd.Series(dtype=float))
        _cx_s   = df_fund.get("capex",             pd.Series(dtype=float)).abs()
        _ni_s   = df_fund.get("net_income",        pd.Series(dtype=float))
        _ebt_s  = df_fund.get("ebt",              pd.Series(dtype=float))
        _tax_s  = df_fund.get("income_tax",        pd.Series(dtype=float))
        _cash_s = df_fund.get("cash",              pd.Series(dtype=float))
        _debt_s = df_fund.get("total_debt",        pd.Series(dtype=float))
        _ar_s   = df_fund.get("accounts_receivable",pd.Series(dtype=float))
        _ap_s   = df_fund.get("accounts_payable",   pd.Series(dtype=float))
        _inv_s  = df_fund.get("inventory",          pd.Series(dtype=float)).fillna(0)
        _sti_s  = df_fund.get("short_term_investments",pd.Series(dtype=float)).fillna(0)

        def _hmean(num, den, n=3):
            idx2 = num.dropna().index.intersection(den.dropna().index)
            if idx2.empty: return np.nan
            r = (num.reindex(idx2)/den.reindex(idx2).replace(0,np.nan)).dropna()
            return float(np.nanmean(r.iloc[-min(n,len(r)):]))

        def _cagr3(s, n=3):
            s = s.dropna()
            if len(s)<2: return np.nan
            n2=min(n,len(s)-1); v0,vn=float(s.iloc[-n2-1]),float(s.iloc[-1])
            return (vn/v0)**(1/n2)-1 if v0>0 else np.nan

        _rev_base = last_valid(_rev_s)
        rev_cagr_auto = float(np.clip(_cagr3(_rev_s,3) or 0.08,-0.05,0.30))
        ebit_margin_def = float(np.clip(_hmean(_ebit_s,_rev_s) or 0.12,0.01,0.60))
        da_pct_def   = float(np.clip(_hmean(_da_s,_rev_s) or 0.03,0.0,0.20))
        capex_pct_def= float(np.clip(_hmean(_cx_s,_rev_s) or 0.04,0.0,0.25))

        # NWC operativo (AR+Inv-AP)/Rev — metodo incrementale come notebook
        nwc_pct_def = 0.05; _nwc_src = "default 5% (AR/AP non disponibili)"
        if not _ar_s.dropna().empty and not _ap_s.dropna().empty:
            _idx_nwc = (_rev_s.dropna().index
                        .intersection(_ar_s.dropna().index)
                        .intersection(_ap_s.dropna().index))
            if not _idx_nwc.empty:
                _op_nwc = _ar_s.reindex(_idx_nwc)+_inv_s.reindex(_idx_nwc).fillna(0)-_ap_s.reindex(_idx_nwc)
                _nwc_r  = (_op_nwc/_rev_s.reindex(_idx_nwc).replace(0,np.nan)).dropna()
                if not _nwc_r.empty:
                    nwc_pct_def = float(np.clip(np.nanmean(_nwc_r.iloc[-3:]),-0.10,0.20))
                    _nwc_src = "NWC operativo (AR+Inv-AP)/Rev, media 3Y"

        # Tax rate effettivo
        tax_rate_dcf = tax_rate_w
        if not _tax_s.dropna().empty and not _ebt_s.dropna().empty:
            _idx_tax2 = _tax_s.dropna().index.intersection(_ebt_s[_ebt_s>0].dropna().index)
            if not _idx_tax2.empty:
                _t2 = (_tax_s.reindex(_idx_tax2).abs()/_ebt_s.reindex(_idx_tax2).abs()).clip(0,0.45)
                tax_rate_dcf = float(np.nanmean(_t2.iloc[-3:]))

        # Bridge values
        _cash_b = float(last_valid(_cash_s) or 0) + float(last_valid(_sti_s) or 0)
        _debt_b = float(last_valid(_debt_s) or 0)
        _sh_b   = float(last_valid(df_fund.get("shares_outstanding",pd.Series(dtype=float))) or shares or 0)

        # Stub period automatico
        _today = datetime.now()
        _yr_end = datetime(_today.year,12,31)
        _stub  = max((_yr_end-_today).days+1,0)/365.0
        _base_yr = int(max(_rev_s.dropna().index)) if not _rev_s.dropna().empty else _today.year-1
        if _base_yr < _today.year-1: _stub=1.0
        elif _base_yr >= _today.year: _stub=0.0

        # Growth defaults: [g1]*3 + [g1*0.65]*3
        _g1_def = float(np.clip(rev_cagr_auto,0.03,0.30))
        _g2_def = float(np.clip(_g1_def*0.65,0.02,0.15))

        # ── Parametri interattivi ─────────────────────────────────────────
        with st.expander("⚙️ Parametri DCF — modifica qui", expanded=False):
            _c1,_c2,_c3 = st.columns(3)
            with _c1:
                dcf_wacc   = st.slider("WACC (%)",4.,20.,float(round(wacc_calc*100,2)),.25,key="dw")/100
                dcf_term_g = st.slider("TGR %",0.5,4.5,2.5,.25,key="dtg")/100
                dcf_years  = st.slider("Anni proiezione",5,10,6,1,key="dy")
            with _c2:
                dcf_ebit  = st.slider("EBIT Margin %",0.,50.,float(round(ebit_margin_def*100,1)),.5,key="de")/100
                dcf_tax   = st.slider("Tax Rate %",10.,45.,float(round(tax_rate_dcf*100,1)),.5,key="dt")/100
                dcf_da    = st.slider("D&A / Revenue %",0.,20.,float(round(da_pct_def*100,1)),.5,key="dda")/100
            with _c3:
                dcf_capex = st.slider("CapEx / Revenue %",0.,25.,float(round(capex_pct_def*100,1)),.5,key="dc")/100
                dcf_nwc   = st.slider("NWC % di ΔRev",−5.,20.,float(round(nwc_pct_def*100,1)),.5,key="dnwc")/100
                g1_sl     = st.slider("Rev Growth Y1-3 %",-5.,35.,float(round(_g1_def*100,1)),.5,key="dg1")
            _cm,_ct = st.columns(2)
            with _cm: mid_yr_on = st.checkbox("Mid-Year Convention",value=True,key="dmid")
            with _ct: tv_exit_w = st.slider("Peso Exit Multiple TV %",0,50,20,5,key="dtev")/100
            exit_ebitda_x = st.slider("Exit EV/EBITDA (x)",5.,25.,16.7,.1,key="devm")

        # Growth schedule [g1]*3 + [g2]*3 come notebook
        _g1=g1_sl/100; _g2=float(np.clip(_g1*0.65,dcf_term_g,_g1))
        _gg = [_g1]*3+[_g2]*3
        dcf_rev_growth = (_gg[:dcf_years] if dcf_years<=6
                          else _gg+[_g2]*(dcf_years-6))

        if not _rev_base or np.isnan(_rev_base):
            st.warning("Revenue non disponibile.")
        elif _sh_b<=0:
            st.warning("Numero azioni non disponibile.")
        else:
            # ── Tabella storica (Cell 37 notebook) ───────────────────────
            _all_yr = sorted(_rev_s.dropna().index)
            if _all_yr:
                def _fc(v,fmt="$B"):
                    if pd.isna(v): return "—"
                    if fmt=="$B": return f"{curr_sym}{v/1e9:.2f}B"
                    if fmt=="%":  return f"{v*100:.1f}%"
                    return str(round(v,2))
                _htbl = {"Revenue":{yr:_fc(_rev_s.get(yr,np.nan),"$B") for yr in _all_yr}}
                if not _ebit_s.dropna().empty:
                    _htbl["EBIT"] = {yr:_fc(_ebit_s.get(yr,np.nan),"$B") for yr in _all_yr}
                    _em_h=(_ebit_s/_rev_s.replace(0,np.nan)).dropna()
                    _htbl["EBIT Margin"]={yr:_fc(_em_h.get(yr,np.nan),"%") for yr in _all_yr}
                if not _da_s.dropna().empty:
                    _htbl["D&A"]={yr:_fc(_da_s.get(yr,np.nan),"$B") for yr in _all_yr}
                    _da_h=(_da_s/_rev_s.replace(0,np.nan)).dropna()
                    _htbl["D&A % Rev"]={yr:_fc(_da_h.get(yr,np.nan),"%") for yr in _all_yr}
                if not _cx_s.dropna().empty:
                    _htbl["CapEx"]={yr:_fc(_cx_s.get(yr,np.nan),"$B") for yr in _all_yr}
                    _cx_h=(_cx_s/_rev_s.replace(0,np.nan)).dropna()
                    _htbl["CapEx % Rev"]={yr:_fc(_cx_h.get(yr,np.nan),"%") for yr in _all_yr}
                with st.expander("📊 Base Storica — calibrazione assunzioni"):
                    st.caption(f"Fonte: {data_source} | NWC: {_nwc_src}")
                    _df_h = pd.DataFrame(_htbl).T
                    _df_h.columns=[str(c) for c in _df_h.columns]
                    st.dataframe(_df_h, use_container_width=True)

            # ── Forecast (Cell 39 notebook — formula IDENTICA) ───────────
            _rows=[]; _rv_t=_rev_base; _rv_p=_rev_base
            _pv_tot=0.0; _disc_f=[]; _ebitda_f=[]; _ufcf_f=[]

            for _i in range(dcf_years):
                _gr  = dcf_rev_growth[_i] if _i<len(dcf_rev_growth) else dcf_term_g
                _rv_t= _rv_p*(1+_gr); _drv=_rv_t-_rv_p
                _ebit_t  = _rv_t*dcf_ebit
                _nopat_t = _ebit_t*(1-dcf_tax)
                _da_t    = _rv_t*dcf_da
                _cx_t    = _rv_t*dcf_capex
                # ΔNWC = DELTA_Revenue × nwc_pct  ← formula notebook (incrementale)
                _dnwc_t  = _drv*dcf_nwc
                _ufcf_t  = _nopat_t+_da_t-_cx_t-_dnwc_t
                _ebitda_t= _ebit_t+_da_t

                if mid_yr_on:
                    if _i==0:
                        _ufcf_t*=_stub; _disc_t=_stub/2.0 if _stub>0 else 0.5
                    else:
                        _disc_t=_stub+(_i-0.5)
                else:
                    _disc_t=float(_i+1)
                _df_t=1.0/(1+dcf_wacc)**_disc_t; _pv_t=_ufcf_t*_df_t
                _pv_tot+=_pv_t
                _disc_f.append(_disc_t); _ebitda_f.append(_ebitda_t); _ufcf_f.append(_ufcf_t)
                _rows.append({
                    "Anno":_today.year+_i+1,"G%":round(_gr*100,1),
                    f"Rev({curr_sym}M)":round(_rv_t/1e6,1),
                    f"EBIT({curr_sym}M)":round(_ebit_t/1e6,1),"EBIT%":round(dcf_ebit*100,1),
                    f"NOPAT({curr_sym}M)":round(_nopat_t/1e6,1),
                    f"D&A({curr_sym}M)":round(_da_t/1e6,1),
                    f"CapEx({curr_sym}M)":round(_cx_t/1e6,1),
                    f"ΔNWC({curr_sym}M)":round(_dnwc_t/1e6,1),
                    f"UFCF({curr_sym}M)":round(_ufcf_t/1e6,1),
                    "DF":round(_df_t,4),f"PV({curr_sym}M)":round(_pv_t/1e6,1),
                })
                _rv_p=_rv_t

            _disc_last=_disc_f[-1] if _disc_f else float(dcf_years)
            _ebitda_last=_ebitda_f[-1] if _ebitda_f else np.nan
            _ufcf_last=_ufcf_f[-1] if _ufcf_f else 0.0

            _df_proj=pd.DataFrame(_rows).set_index("Anno")
            with st.expander("📋 Forecast UFCF anno per anno"):
                st.dataframe(_df_proj.style.format({"G%":"{:.1f}%","EBIT%":"{:.1f}%","DF":"{:.4f}",
                    **{c:"{:,.1f}" for c in _df_proj.columns if c not in("G%","EBIT%","DF")}}),
                    use_container_width=True)

            # ── Terminal Value + Equity Bridge (Cell 41) ─────────────────
            if dcf_wacc>dcf_term_g:
                _TV_p  = _ufcf_last*(1+dcf_term_g)/(dcf_wacc-dcf_term_g)
                _PV_p  = _TV_p/(1+dcf_wacc)**_disc_last
                _TV_e  = (_ebitda_last*exit_ebitda_x if not np.isnan(_ebitda_last) else _TV_p)
                _PV_e  = _TV_e/(1+dcf_wacc)**_disc_last
                _pw    = 1.0-tv_exit_w
                _TV    = _pw*_TV_p+tv_exit_w*_TV_e
                _PV_TV = _pw*_PV_p+tv_exit_w*_PV_e
            else:
                _TV=_PV_TV=0.0
                st.error(f"WACC ({dcf_wacc*100:.1f}%) deve essere > TGR ({dcf_term_g*100:.1f}%)")

            _EV   = _pv_tot+_PV_TV
            _eq   = _EV+_cash_b-_debt_b
            intrinsic_price_dcf = _eq/_sh_b
            fair_values["DCF (UFCF)"] = intrinsic_price_dcf
            _tv_pct = _PV_TV/_EV*100 if _EV>0 else np.nan

            # KPI
            _k1,_k2,_k3,_k4=st.columns(4)
            _delta=(price/intrinsic_price_dcf-1)*100 if price and intrinsic_price_dcf else 0
            with _k1: card("EV (DCF)",fmt_m(_EV,sym=curr_sym),ACCENT)
            with _k2: card("Equity Value",fmt_m(_eq,sym=curr_sym),PURPLE)
            with _k3: card("Prezzo Intrinseco",f"{curr_sym}{intrinsic_price_dcf:.2f}",
                           GREEN if price<=intrinsic_price_dcf else RED)
            with _k4: card("vs Mercato",f"{_delta:+.1f}%",RED if _delta>0 else GREEN)

            with st.expander("📊 Equity Bridge dettaglio"):
                _br={
                    "PV Flussi Espliciti":    f"{curr_sym}{_pv_tot/1e9:.2f}B",
                    "TV Gordon Growth":        f"{curr_sym}{_TV_p/1e9:.2f}B",
                    "TV Exit Multiple":        f"{curr_sym}{_TV_e/1e9:.2f}B  ({exit_ebitda_x:.1f}x EBITDA)",
                    f"PV TV Blended ({_pw*100:.0f}%G/{tv_exit_w*100:.0f}%E)":
                                               f"{curr_sym}{_PV_TV/1e9:.2f}B  ({_tv_pct:.1f}% EV)" if not np.isnan(_tv_pct) else "N/A",
                    "Enterprise Value":        f"{curr_sym}{_EV/1e9:.2f}B",
                    "+ Cash & ST Investments": f"{curr_sym}{_cash_b/1e9:.2f}B",
                    "- Total Debt":            f"{curr_sym}{_debt_b/1e9:.2f}B",
                    "= Equity Value":          f"{curr_sym}{_eq/1e9:.2f}B",
                    "/ Diluted Shares":        f"{_sh_b/1e6:.1f}M",
                    "→ Fair Value / Share":    f"{curr_sym}{intrinsic_price_dcf:.2f}",
                }
                for _bk,_bv in _br.items():
                    st.markdown(f"**{_bk}**: `{_bv}`")

            # ── 4 Grafici (replica Cell 42 notebook) ─────────────────────
            st.markdown("")
            _rev_hy=[yr for yr in sorted(_rev_s.dropna().index)]
            _rev_hv=[_rev_s[yr]/1e9 for yr in _rev_hy]
            _rev_fy=[_today.year+i+1 for i in range(dcf_years)]
            _rv2=_rev_base
            _rev_fv=[]
            for _i2 in range(dcf_years):
                _gr2=dcf_rev_growth[_i2] if _i2<len(dcf_rev_growth) else dcf_term_g
                _rv2=_rv2*(1+_gr2); _rev_fv.append(_rv2/1e9)
            _ufcf_m=[r[f"UFCF({curr_sym}M)"] for r in _rows]
            _pv_m  =[r[f"PV({curr_sym}M)"] for r in _rows]
            _yrs_r =[r["Anno"] for r in _rows]

            fig_dcf=make_subplots(rows=2,cols=2,subplot_titles=[
                f"Revenue Storico + Forecast ({curr_sym}B)",
                f"UFCF & PV(UFCF) ({curr_sym}M)",
                f"Composizione EV ({curr_sym}B)",
                "TV vs PV UFCF (%)",
            ],specs=[[{"type":"xy"},{"type":"xy"}],
                     [{"type":"xy"},{"type":"domain"}]])
            fig_dcf.add_trace(go.Scatter(x=list(_rev_hy),y=_rev_hv,mode="lines+markers",
                name="Storico",line=dict(color=ACCENT,width=2.5),marker=dict(size=7)),row=1,col=1)
            fig_dcf.add_trace(go.Scatter(x=_rev_fy,y=_rev_fv,mode="lines+markers",
                name="Forecast",line=dict(color=GREEN,width=2.5,dash="dash"),marker=dict(size=7)),row=1,col=1)
            if _rev_hy:
                fig_dcf.add_vline(x=_rev_hy[-1],line_dash="dot",line_color=MUTED,
                                  line_width=1,row=1,col=1)
            fig_dcf.add_trace(go.Bar(x=_yrs_r,y=_ufcf_m,name="UFCF",
                marker_color=ACCENT,opacity=0.8),row=1,col=2)
            fig_dcf.add_trace(go.Bar(x=_yrs_r,y=_pv_m,name="PV(UFCF)",
                marker_color=GREEN,opacity=0.7),row=1,col=2)
            _wf_v=[_pv_tot/1e9,_PV_TV/1e9,_EV/1e9]
            _wf_l=["PV UFCF","PV TV","EV"]
            fig_dcf.add_trace(go.Bar(x=_wf_l,y=_wf_v,name="EV Bridge",
                marker_color=[ACCENT,PURPLE,ORANGE],opacity=0.85,
                text=[f"{curr_sym}{v:.1f}B" for v in _wf_v],
                textposition="outside"),row=2,col=1)
            if _pv_tot>0 and _PV_TV>0:
                fig_dcf.add_trace(go.Pie(
                    labels=[f"PV UFCF\n{curr_sym}{_pv_tot/1e9:.1f}B",
                            f"PV TV\n{curr_sym}{_PV_TV/1e9:.1f}B"],
                    values=[_pv_tot,_PV_TV],marker_colors=[ACCENT,PURPLE],
                    hole=0.4,showlegend=True),row=2,col=2)
            fig_dcf.update_layout(**LAYOUT,height=680,
                title=f"{company_name} — DCF Valuation Summary")
            plo(fig_dcf)

            # ── Sensitivity WACC × TGR (Cell 44 notebook) ────────────────
            st.markdown("")
            section("🔥","Sensitivity — WACC × Terminal Growth Rate")

            def _eng(w,tg,rb,gg,em,t,da,cx,nwc,n,sh,ca,db,st2=1.0,mid=False,ex=0.,pw=1.,ew=0.):
                if w<=tg or not rb or np.isnan(rb): return np.nan
                _p=0.;_rv=rb;_rp=rb;_el=np.nan
                for _ii in range(n):
                    _gr=gg[_ii] if _ii<len(gg) else gg[-1]
                    _rv=_rp*(1+_gr);_dr=_rv-_rp
                    _u=_rv*em*(1-t)+_rv*da-_rv*cx-_dr*nwc;_el=_rv*em+_rv*da
                    if mid:
                        _d=st2/2 if _ii==0 else st2+(_ii-0.5)
                        if _ii==0:_u*=st2
                    else: _d=float(_ii+1)
                    _p+=_u/(1+w)**_d;_rp=_rv
                _dT=st2+n-0.5 if mid else float(n)
                _uT=_rv*em*(1-t)+_rv*da-_rv*cx
                _tvp=_uT*(1+tg)/(w-tg);_tve=(_el*ex) if (ex>0 and not np.isnan(_el)) else 0
                _tv=pw*_tvp+ew*_tve
                return (_p+_tv/(1+w)**_dT+ca-db)/sh if sh>0 else np.nan

            # Grid WACC: base-2% to base+3%, step 0.5% | TGR: 1%-4%, step 0.5%
            _wg=np.arange(max(dcf_wacc-0.02,0.04),dcf_wacc+0.031,0.005)
            _tg=np.arange(0.010,0.045,0.005)
            _sm={}
            for _tgv in _tg:
                _row={}
                for _wv in _wg:
                    _row[round(_wv*100,1)]=_eng(_wv,_tgv,_rev_base,dcf_rev_growth,
                        dcf_ebit,dcf_tax,dcf_da,dcf_capex,dcf_nwc,dcf_years,
                        _sh_b,_cash_b,_debt_b,_stub,mid_yr_on,
                        exit_ebitda_x,1-tv_exit_w,tv_exit_w)
                _sm[round(_tgv*100,1)]=_row
            _df_s=pd.DataFrame(_sm).T; _df_s.index.name="TGR\\WACC"

            _zv=_df_s.values.tolist()
            _zt=[[(v/price if price and not(isinstance(v,float) and np.isnan(v)) else 0.5)
                  for v in row] for row in _zv]
            _ztxt=[[f"{curr_sym}{v:.0f}" if not(isinstance(v,float) and np.isnan(v)) else "N/A"
                    for v in row] for row in _zv]
            fig_s1=go.Figure(go.Heatmap(
                z=_zt,x=[f"{c:.1f}%" for c in _df_s.columns],
                y=[f"{i:.1f}%" for i in _df_s.index],
                colorscale=[[0,"#f78166"],[0.5,"#ffa657"],[0.9,"#3fb950"],[1,"#1a7f37"]],
                text=_ztxt,texttemplate="%{text}",showscale=False,zmin=0.5,zmax=1.5))
            fig_s1.add_annotation(
                text=f"Base: WACC={dcf_wacc*100:.2f}% / TGR={dcf_term_g*100:.1f}% → {curr_sym}{intrinsic_price_dcf:.0f} | Prezzo: {curr_sym}{price:.0f}",
                xref="paper",yref="paper",x=0.5,y=1.06,showarrow=False,
                font=dict(color=TEXT_C,size=11))
            fig_s1.update_layout(**LAYOUT,height=420,
                xaxis_title="WACC",yaxis_title="Terminal Growth Rate",
                title="Sensitivity 1 — Prezzo Implicito/Share (verde=upside, rosso=downside)")
            plo(fig_s1)

            # Sensitivity 2 — Rev Growth × EBIT Margin
            st.markdown("")
            section("🔥","Sensitivity 2 — Rev Growth Anno 1 × EBIT Margin")
            _rg2=[max(_g1-0.04+i*0.02,-0.05) for i in range(5)]
            _em2=[max(dcf_ebit-0.04+i*0.02,0.01) for i in range(5)]
            _h2=[]
            for _rg in _rg2:
                _row2=[]
                for _em in _em2:
                    _gg2=[_rg]*3+[float(np.clip(_rg*0.65,dcf_term_g,_rg))]*max(dcf_years-3,0)
                    _gg2=(_gg2[:dcf_years] if len(_gg2)>=dcf_years
                          else _gg2+[_gg2[-1]]*(dcf_years-len(_gg2)))
                    _row2.append(_eng(dcf_wacc,dcf_term_g,_rev_base,_gg2,
                        _em,dcf_tax,dcf_da,dcf_capex,dcf_nwc,dcf_years,
                        _sh_b,_cash_b,_debt_b,_stub,mid_yr_on,
                        exit_ebitda_x,1-tv_exit_w,tv_exit_w))
                _h2.append(_row2)
            _df_h2=pd.DataFrame(_h2,index=[f"{g*100:.1f}%" for g in _rg2],
                                 columns=[f"{e*100:.1f}%" for e in _em2])
            _z2=_df_h2.values.tolist()
            _zt2=[[(v/price if price and not(isinstance(v,float) and np.isnan(v)) else 0.5)
                   for v in row] for row in _z2]
            _ztxt2=[[f"{curr_sym}{v:.0f}" if not(isinstance(v,float) and np.isnan(v)) else "N/A"
                     for v in row] for row in _z2]
            fig_s2=go.Figure(go.Heatmap(
                z=_zt2,x=_df_h2.columns.tolist(),y=_df_h2.index.tolist(),
                colorscale=[[0,"#f78166"],[0.5,"#ffa657"],[0.9,"#3fb950"],[1,"#1a7f37"]],
                text=_ztxt2,texttemplate="%{text}",showscale=False,zmin=0.5,zmax=1.5))
            fig_s2.update_layout(**LAYOUT,height=380,
                xaxis_title="EBIT Margin",yaxis_title="Rev Growth Anno 1",
                title="Sensitivity 2 — Prezzo Implicito (Rev Growth × EBIT Margin)")
            plo(fig_s2)

        # ── FCFE Model ──────────────────────────────────────────────────────
        st.markdown("")
        section("💰","FCFE — Free Cash Flow to Equity")
        _sh_fcfe = float(last_valid(df_fund.get("shares_outstanding",pd.Series(dtype=float))) or shares or 0)
        _ni_fc   = last_valid(df_fund.get("net_income",pd.Series()))
        _da_fc   = last_valid(df_fund.get("depreciation",pd.Series()))
        _cx_fc   = last_valid(df_fund.get("capex",pd.Series()))
        _rev_fc  = last_valid(df_fund.get("revenue",pd.Series()))
        _debt_fc = last_valid(df_fund.get("total_debt",pd.Series())) or 0
        _cash_fc = last_valid(df_fund.get("cash",pd.Series())) or 0

        if _ni_fc and _sh_fcfe>0 and not np.isnan(_ni_fc):
            _da_v  = abs(_da_fc) if not pd.isna(_da_fc or np.nan) else (_rev_fc or 0)*da_pct_def
            _cx_v  = abs(_cx_fc) if not pd.isna(_cx_fc or np.nan) else (_rev_fc or 0)*capex_pct_def
            _dnwc_v= (_rev_fc or 0)*rev_cagr_auto*nwc_pct_def
            _fcfe0 = _ni_fc+_da_v-_cx_v-_dnwc_v+_debt_fc*0.04
            _g1f=float(np.clip(rev_cagr_auto,0.01,0.25)); _g2f=dcf_term_g; _kef=ke_calc; _nf=6
            if _kef>_g1f and _kef>_g2f:
                _pvf=0.;_ft=_fcfe0
                for _tf in range(1,_nf+1):
                    _ft=_ft*(1+_g1f);_pvf+=_ft/(1+_kef)**_tf
                _TVf=_ft*(1+_g2f)/(_kef-_g2f);_PVTVf=_TVf/(1+_kef)**_nf
                _fcfe_px=(_pvf+_PVTVf+_cash_fc)/_sh_fcfe
                fair_values["FCFE"]=_fcfe_px
                _f1,_f2,_f3,_f4=st.columns(4)
                _fups=(_fcfe_px/price-1)*100 if price else 0
                with _f1: card("FCFE base",fmt_m(_fcfe0,sym=curr_sym),ACCENT)
                with _f2: card("TV Gordon",fmt_m(_TVf,sym=curr_sym),PURPLE)
                with _f3: card("Fair Value FCFE",f"{curr_sym}{_fcfe_px:.2f}",
                               GREEN if price<=_fcfe_px else RED)
                with _f4: card("Upside FCFE",f"{_fups:+.1f}%",GREEN if _fups>0 else RED)
                with st.expander("ℹ️ Assunzioni FCFE"):
                    st.markdown(f"""
- **FCFE** = NI + D&A − CapEx − ΔNWC + Net Borrow = {curr_sym}{_fcfe0/1e6:.0f}M
- **g1** = {_g1f*100:.1f}% · **g2** = {_g2f*100:.1f}% · **ke** = {_kef*100:.2f}% (CAPM)
- **TV** = FCFE_n×(1+g2)/(ke−g2) = {curr_sym}{_TVf/1e9:.2f}B
- **PV TV** = {curr_sym}{_PVTVf/1e9:.2f}B · **PV flussi** = {curr_sym}{_pvf/1e9:.2f}B
""")
            else:
                st.info("FCFE non calcolabile: ke ≤ g.")
        else:
            st.info("Dati insufficienti per FCFE.")

        # ── DDM a Due Stadi ─────────────────────────────────────────────────
        st.markdown("")
        section("💵","DDM a Due Stadi (replica DCF gg.xlsx)")
        _sh_ddm = float(last_valid(df_fund.get("shares_outstanding",pd.Series(dtype=float))) or shares or 1)
        _div0   = float(mkt.get("dividendPerShare") or mkt.get("dividendRate") or 0)
        if _div0<=0 and price:
            _dy_v=float(mkt.get("dividendYield") or 0)
            if _dy_v>0: _div0=price*_dy_v
        if _div0<=0:
            _ni_ddm=last_valid(df_fund.get("net_income",pd.Series()))
            if _ni_ddm and not np.isnan(_ni_ddm) and _sh_ddm>0:
                _div0=_ni_ddm/_sh_ddm*0.40

        if _div0>0 and ke_calc>0:
            _roe_ddm=np.nan
            if "net_income" in df_fund.columns and "total_equity" in df_fund.columns:
                _ni_d=df_fund["net_income"].dropna();_eq_d=df_fund["total_equity"].dropna()
                _ix_d=_ni_d.index.intersection(_eq_d.index)
                if len(_ix_d)>0:
                    _roe_ddm=float((_ni_d.reindex(_ix_d)/_eq_d.reindex(_ix_d).replace(0,np.nan)).iloc[-3:].mean())
            _pay=float(np.clip(1-(_div0/max(
                safe_div(last_valid(df_fund.get("net_income",pd.Series())),_sh_ddm) or _div0,0.01)),0.10,0.95))
            _g1d=float(np.clip((_roe_ddm or 0.12)*(1-_pay),0.02,0.20))
            _g2d=float(np.clip(dcf_term_g,0.01,ke_calc-0.01))
            _nd=6
            if ke_calc>_g1d and ke_calc>_g2d:
                _pvd=0.;_dt=_div0
                for _td in range(1,_nd+1):
                    _dt=_dt*(1+_g1d);_pvd+=_dt/(1+ke_calc)**_td
                _TVd=_dt*(1+_g2d)/(ke_calc-_g2d);_PVTVd=_TVd/(1+ke_calc)**_nd
                _ddm_px=_pvd+_PVTVd
                fair_values["DDM 2-stage"]=_ddm_px
                _dd1,_dd2,_dd3,_dd4=st.columns(4)
                _ddm_ups=(_ddm_px/price-1)*100 if price else 0
                with _dd1: card("D0/Share",f"{curr_sym}{_div0:.2f}",ACCENT)
                with _dd2: card("g1 / g2",f"{_g1d*100:.1f}% / {_g2d*100:.1f}%",ORANGE)
                with _dd3: card("Fair Value DDM",f"{curr_sym}{_ddm_px:.2f}",
                               GREEN if price<=_ddm_px else RED)
                with _dd4: card("Upside DDM",f"{_ddm_ups:+.1f}%",GREEN if _ddm_ups>0 else RED)
                with st.expander("ℹ️ Assunzioni DDM"):
                    st.markdown(f"""
- **D0** = {curr_sym}{_div0:.2f} · ROE = {(_roe_ddm or 0)*100:.1f}% · payout = {_pay*100:.0f}%
- **g1** = {_g1d*100:.1f}% (ROE×retention) · **g2** = {_g2d*100:.1f}% · ke = {ke_calc*100:.2f}%
- **TV** = D_n×(1+g2)/(ke−g2) = {curr_sym}{_TVd:.2f}/share
- **PV div S1** = {curr_sym}{_pvd:.2f} · **PV TV** = {curr_sym}{_PVTVd:.2f}
""")
            else:
                st.info("DDM non calcolabile: ke ≤ g.")
        else:
            st.info("Nessun dividendo — DDM non applicabile.")

        # ── P/E fair value ─────────────────────────────────────────────────
        _ni_pe=last_valid(df_fund.get("net_income",pd.Series()))
        _sh_pe=float(last_valid(df_fund.get("shares_outstanding",pd.Series(dtype=float))) or shares or 0)
        if _ni_pe and _ni_pe>0 and _sh_pe>0:
            _eps_pe=_ni_pe/_sh_pe
            _fpe=min(max(rev_cagr_5y*100*2 if not pd.isna(rev_cagr_5y) else 20,12),35)
            fair_values["P/E storico"]=_eps_pe*_fpe

        # ── Grafico tutti i metodi ─────────────────────────────────────────
        _fvall={k:v for k,v in fair_values.items() if v and not pd.isna(v) and v>0}
        if _fvall and price:
            _fvmed=float(np.median(list(_fvall.values())))
            _prem=(price-_fvmed)/_fvmed; _entry=_fvmed*0.80
            st.markdown("")
            section("⚖️","Confronto Fair Value — Tutti i Metodi")
            _figfv=go.Figure()
            for _mk,_fvv in _fvall.items():
                _figfv.add_trace(go.Bar(name=_mk,x=[_mk],y=[_fvv],
                    marker_color=GREEN if price<=_fvv else RED,opacity=.85,
                    text=f"{curr_sym}{_fvv:.0f}",textposition="outside"))
            _figfv.add_hline(y=price,line_color=ACCENT,line_dash="dash",
                             annotation_text=f"Prezzo {curr_sym}{price:.2f}",line_width=2)
            _figfv.add_hline(y=_entry,line_color=ORANGE,line_dash="dot",
                             annotation_text=f"MOS 20% {curr_sym}{_entry:.2f}",line_width=1.5)
            _figfv.update_layout(**LAYOUT,height=420,yaxis_title=f"Fair Value ({curr_sym})",
                                 title="Fair Value — Confronto Multi-Metodo")
            plo(_figfv)
            _fv1,_fv2,_fv3=st.columns(3)
            with _fv1: card("Fair Value mediana",f"{curr_sym}{_fvmed:.2f}",GREEN)
            with _fv2: card("Prezzo",f"{curr_sym}{price:.2f}",ACCENT)
            with _fv3:
                _lp="PREMIUM" if _prem>0 else "SCONTO"
                card(_lp,f"{abs(_prem)*100:.1f}%",RED if _prem>0 else GREEN)
    else:
        st.info("Prezzo non disponibile per il calcolo DCF.")
