from __future__ import annotations

import pandas as pd
import streamlit as st

from core import harmonic_wavelengths, overlap_table, classify_overlap
from fpbase_adapter import fetch_fluorophore, list_fluorophore_names
from plotting import make_excitation_figure, make_emission_harmonic_figure
from store import (init_store, read_fluorophores, read_spectra,
                   upsert_fluorophore, delete_fluorophore, import_custom_long_csv)

st.set_page_config(page_title='STELLARIS Spectral Planner', page_icon='🔬', layout='wide')
st.markdown('''<style>
.block-container {padding-top:1rem;padding-bottom:1rem;max-width:1550px;}
div[data-testid="stVerticalBlock"] {gap:0.55rem;}
h1 {margin-bottom:0.1rem;}
</style>''', unsafe_allow_html=True)
init_store()
st.title('STELLARIS DIVE Spectral Planner')
st.caption('Full 1P/2P spectra with SHG, THG and 4Tune detection bands.')

@st.cache_data(ttl=86400, show_spinner=False)
def catalogue():
    return list_fluorophore_names()

@st.cache_data(ttl=86400, show_spinner=False)
def remote_spectra(name):
    return fetch_fluorophore(name)

NONE = '— None —'

def ensure_local(name):
    aliases = st.session_state.setdefault('fp_aliases', {})
    canonical = aliases.get(name, name)
    local = read_spectra()
    if canonical in local['name'].astype(str).values:
        return canonical
    meta, curves = remote_spectra(name)
    if curves.empty:
        raise ValueError('FPbase returned no usable spectral curves.')
    upsert_fluorophore(meta, curves)
    aliases[name] = meta['name']
    return meta['name']

st.sidebar.header('Excitation')
mp_excitation = st.sidebar.slider('Multiphoton excitation (nm)', 680, 1300, 1040, 1)
shg_nm, thg_nm = harmonic_wavelengths(mp_excitation)
shg_round, thg_round = int(shg_nm + .5), int(thg_nm + .5)
c1, c2 = st.sidebar.columns(2)
c1.metric('SHG', f'{shg_round} nm')
c2.metric('THG', f'{thg_round} nm')
st.sidebar.caption(f'10 nm guide bands: SHG {shg_round-5}–{shg_round+5} nm · THG {thg_round-5}–{thg_round+5} nm')
outside = [f'{label} {int(w+.5)} nm' for label,w in [('SHG',shg_nm),('THG',thg_nm)] if not 380 <= w <= 800]
if outside:
    st.sidebar.caption('Outside nominal detector range (380–800 nm): ' + ', '.join(outside))
st.sidebar.subheader('Optional 1P markers')
one_p_lines = st.sidebar.multiselect('Laser lines', [375,405,473,488,552,561,594,633,640], default=[405,488,561])
show_1p = st.sidebar.checkbox('Show 1P excitation', True)
show_2p = st.sidebar.checkbox('Show measured 2P excitation', True)
show_harmonic_bands = st.sidebar.checkbox('Show 10 nm SHG/THG bands', True)

# Callbacks execute before widgets are created on the next run.
def tune_changed(i, moved):
    lo_key, hi_key = f'tune_low_{i}', f'tune_high_{i}'
    lo, hi = st.session_state[lo_key], st.session_state[hi_key]
    if hi - lo < 10:
        if moved == 'high':
            hi = max(390, hi)
            lo = hi - 10
        else:
            lo = min(790, lo)
            hi = lo + 10
    st.session_state[lo_key], st.session_state[hi_key] = lo, hi

st.sidebar.subheader('4Tune windows')
show_4tune = st.sidebar.checkbox('Show 4Tune bands', True)
tune_windows = []
for i, (default_lo, default_hi) in enumerate([(420,480),(490,550),(560,620),(630,700)], 1):
    lo_key, hi_key = f'tune_low_{i}', f'tune_high_{i}'
    if lo_key not in st.session_state or hi_key not in st.session_state:
        lo, hi = st.session_state.get(f'tune_ch_{i}', (default_lo,default_hi))
        lo = max(380, min(790, lo))
        hi = min(800, max(lo+10, hi))
        st.session_state[lo_key], st.session_state[hi_key] = lo, hi
    with st.sidebar.expander(f'Ch {i}: {st.session_state[lo_key]}–{st.session_state[hi_key]} nm', expanded=True):
        visible = st.checkbox(f'Show Ch {i}', True, key=f'tune_visible_{i}')
        lo = st.slider('Low (nm)', 380, 790, key=lo_key, on_change=tune_changed, args=(i,'low'))
        hi = st.slider('High (nm)', 390, 800, key=hi_key, on_change=tune_changed, args=(i,'high'))
    if show_4tune and visible:
        tune_windows.append((f'Ch {i}',lo,hi))

st.markdown('#### Fluorophores')
if st.button('Refresh FPbase catalogue'):
    catalogue.clear()
try:
    st.session_state['fp_catalogue'] = catalogue()
except Exception as e:
    st.warning(f'FPbase catalogue unavailable: {e}. Local spectra remain available.')
fluor = read_fluorophores()
local_names = fluor['name'].dropna().astype(str).unique().tolist()
options = [NONE] + sorted(set(local_names) | set(st.session_state.get('fp_catalogue', [])), key=str.lower)
deleted = st.session_state.pop('deleted_fluor', None)
if deleted:
    for i in range(1,5):
        key = f'fluor_slot_{i}'
        value = st.session_state.get(key)
        if value == deleted or st.session_state.get('fp_aliases', {}).get(value) == deleted:
            st.session_state[key] = NONE
pending = st.session_state.pop('pending_fluor', None)
if pending:
    for i in range(1,5):
        if st.session_state.get(f'fluor_slot_{i}', NONE) == NONE:
            st.session_state[f'fluor_slot_{i}'] = pending
            break
selected = []
for i, col in enumerate(st.columns(4),1):
    key = f'fluor_slot_{i}'
    if st.session_state.get(key) not in options:
        st.session_state[key] = NONE
    with col:
        value = st.selectbox(f'Fluorophore {i}', options, key=key)
        if value == NONE:
            continue
        try:
            with st.spinner(f'Loading {value}…'):
                canonical = ensure_local(value)
            spectra = read_spectra()
            types = spectra.loc[spectra['name'] == canonical,'spectrum_type'].astype(str)
            labels = []
            if types.isin(['EX_1P','AB_1P']).any(): labels.append('1P')
            if (types == 'EX_2P').any(): labels.append('2P')
            if (types == 'EM').any(): labels.append('EM')
            st.caption(' · '.join(labels) if labels else 'No spectra')
            if canonical not in selected: selected.append(canonical)
        except Exception as e:
            st.error(f'{value}: {e}')
spectra = read_spectra()
if not selected:
    st.info('Choose up to four fluorophores above to display their spectra.')

# Plot even with no selected fluorophore: harmonic and detector guides remain useful.
ex_fig = make_excitation_figure(spectra, selected, mp_excitation, one_p_lines, show_1p, show_2p)
em_fig = make_emission_harmonic_figure(spectra, selected, mp_excitation, tune_windows=tune_windows, show_harmonic_bands=show_harmonic_bands)
em_fig.update_xaxes(range=[375,800])
left,right = st.columns(2,gap='small')
with left:
    st.markdown('##### Excitation')
    st.plotly_chart(ex_fig,use_container_width=True)
with right:
    st.markdown('##### Emission + SHG / THG')
    st.plotly_chart(em_fig,use_container_width=True)
if selected:
    with st.expander('Spectral overlap results',expanded=True):
        ov = overlap_table(spectra,selected,mp_excitation)
        if not ov.empty:
            ov['SHG overlap'] = ov['Emission @ SHG'].apply(classify_overlap)
            ov['THG overlap'] = ov['Emission @ THG'].apply(classify_overlap)
            ov['SHG nm'],ov['THG nm'] = shg_round,thg_round
            for label,w in [('SHG',shg_round),('THG',thg_round)]:
                ov.insert(ov.columns.get_loc(f'{label} nm')+1,f'{label} 10 nm band',f'{w-5}–{w+5}')
            for col in ['Emission @ SHG','Emission @ THG']:
                ov[col] = ov[col].apply(lambda x: '' if pd.isna(x) else f'{float(x):.2f}')
            st.dataframe(ov,use_container_width=True,hide_index=True)
        st.caption('Normalized emission at the harmonic wavelength indicates spectral collision, not absolute fluorescence versus harmonic brightness.')
    missing = [n for n in selected if spectra[(spectra['name']==n)&(spectra['spectrum_type']=='EX_2P')].empty]
    if missing:
        st.info('No measured 2P spectrum stored for: '+', '.join(missing)+'. No 2P curve is estimated from the 1P spectrum.')

st.divider()
tab1,tab2,tab3 = st.tabs(['Import from FPbase','Add custom spectrum','Local library'])
with tab1:
    st.caption('The four dropdowns above automatically import FPbase spectra. Use this field for a name not listed.')
    fp_name = st.text_input('Type FPbase name',placeholder='e.g. mCherry, EGFP, TagRFP')
    if st.button('Import + add'):
        if not fp_name.strip(): st.error('Enter a fluorophore name.')
        else:
            try:
                canonical = ensure_local(fp_name.strip())
                if canonical in selected or all(st.session_state.get(f'fluor_slot_{i}',NONE)!=NONE for i in range(1,5)):
                    st.success(f'Imported {canonical}. Available in the local library and dropdowns.')
                    # Rerun to refresh dropdown options without replacing existing selections.
                    st.rerun()
                else:
                    st.session_state['pending_fluor'] = canonical
                    st.rerun()
            except Exception as e: st.error(f'FPbase import failed: {e}')
with tab2:
    st.caption('Add fluorophores/dyes missing from FPbase or replace/add a measured 2P curve.')
    st.markdown('**Required columns:** `name, spectrum_type, wavelength_nm, intensity`  \n`spectrum_type`: `EX_1P`, `AB_1P`, `EM`, or `EX_2P`.')
    template = pd.DataFrame([('Example','EX_1P',400,.05),('Example','EX_1P',401,.06),('Example','EM',500,.10),('Example','EM',501,.12)],columns=['name','spectrum_type','wavelength_nm','intensity'])
    st.download_button('Download custom CSV template',template.to_csv(index=False).encode(),'custom_spectrum_template.csv','text/csv')
    upload = st.file_uploader('Upload custom long-format CSV',type=['csv'])
    if upload is not None:
        custom = pd.read_csv(upload)
        st.dataframe(custom.head(20),use_container_width=True)
        if st.button('Add custom spectrum(s)'):
            try:
                import_custom_long_csv(custom)
                st.rerun()
            except Exception as e: st.error(str(e))
with tab3:
    fluor,spectra = read_fluorophores(),read_spectra()
    st.dataframe(fluor,use_container_width=True,hide_index=True)
    if not fluor.empty:
        delete_name = st.selectbox('Remove local entry',['']+fluor['name'].astype(str).tolist())
        if delete_name and st.button(f'Delete {delete_name}'):
            local_id = fluor.loc[fluor['name'].astype(str)==delete_name,'local_id'].iloc[0]
            delete_fluorophore(str(local_id))
            # Clear selected entries before widgets are instantiated again.
            st.session_state['deleted_fluor'] = delete_name
            st.rerun()
        a,b = st.columns(2)
        a.download_button('Export fluorophore metadata',fluor.to_csv(index=False).encode(),'fluorophores.csv','text/csv',use_container_width=True)
        b.download_button('Export full spectra',spectra.to_csv(index=False).encode(),'spectra.csv','text/csv',use_container_width=True)
st.caption('v0.22 · automatic FPbase catalogue · independent 4Tune bands · 10 nm minimum bandwidth')
