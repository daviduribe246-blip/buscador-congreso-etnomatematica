import streamlit as st
import pandas as pd
import re
import unicodedata
from pathlib import Path

st.set_page_config(page_title='Consulta de inscritos | III CCE', page_icon='🔎', layout='centered')

BASE = Path(__file__).parent
PARTICIPANTES = BASE / 'participantes.xlsx'
PONENCIAS = BASE / 'ponencias.xlsx'
LOGO = BASE / 'logo_congreso.jpg'
CERTIFICADOS = BASE / 'certificados_drive.csv'


def normalizar(txt):
    if pd.isna(txt): return ''
    txt = str(txt).strip().lower()
    txt = ''.join(c for c in unicodedata.normalize('NFD', txt) if unicodedata.category(c) != 'Mn')
    txt = re.sub(r'[^a-z0-9 ]+', ' ', txt)
    return re.sub(r'\s+', ' ', txt).strip()


def id_limpia(v):
    if pd.isna(v): return ''
    s = str(v).strip()
    if s.endswith('.0'): s = s[:-2]
    return re.sub(r'\D', '', s)


def dividir_nombre(nombre):
    """Heurística visual: conserva el nombre completo y separa hasta 4 campos.
    Para nombres hispanos de 4+ palabras toma los dos últimos como apellidos."""
    partes = str(nombre).strip().split()
    if not partes: return '', '', '', ''
    if len(partes) == 1: return partes[0], '', '', ''
    if len(partes) == 2: return partes[0], '', partes[1], ''
    if len(partes) == 3: return partes[0], '', partes[1], partes[2]
    nombres = partes[:-2]
    return nombres[0], ' '.join(nombres[1:]), partes[-2], partes[-1]

@st.cache_data
def cargar():
    p = pd.read_excel(PARTICIPANTES, sheet_name='Form Responses 1', dtype=str)
    po = pd.read_excel(PONENCIAS, sheet_name='Form Responses 1', dtype=str)
    p = p.rename(columns={
        'Nombre completo.':'nombre_completo',
        'Número de identificación':'identificacion',
        'Correo':'correo',
        'Filiación Institucional:  (Nombre de la universidad, colegio, institución, etc.) ':'institucion'
    })
    po = po.rename(columns={
        'Nombre autor responsable para comunicación':'autor',
        'Título de la ponencia\nEl título debe ser corto, específico e informativo.':'titulo'
    })

    p['nombre_norm'] = p['nombre_completo'].map(normalizar)
    p['id_norm'] = p['identificacion'].map(id_limpia)
    po['autor_norm'] = po['autor'].map(normalizar)

    # Agrupa todas las ponencias de cada autor responsable.
    titulos = (po.dropna(subset=['autor'])
                 .groupby('autor_norm')['titulo']
                 .apply(lambda x: [str(t).strip() for t in x if pd.notna(t) and str(t).strip()])
                 .to_dict())

    # 1) Personas registradas en el formulario general de participación.
    p['titulos'] = p['nombre_norm'].map(lambda x: titulos.get(x, []))
    p['ponente'] = p['titulos'].map(bool)
    p['origen'] = 'Inscripción general'

    # 2) Autores que están en ponencias pero NO aparecen en el formulario general.
    # Se agregan a la base de búsqueda para que nunca desaparezca un ponente.
    nombres_participantes = set(p['nombre_norm'])
    autores_faltantes = (po[(po['autor_norm'] != '') & (~po['autor_norm'].isin(nombres_participantes))]
                         .drop_duplicates(subset=['autor_norm'])
                         .copy())

    if not autores_faltantes.empty:
        extra = pd.DataFrame({
            'nombre_completo': autores_faltantes['autor'].astype(str).str.strip(),
            'identificacion': '',
            'correo': '',
            'institucion': '',
            'nombre_norm': autores_faltantes['autor_norm'],
            'id_norm': '',
            'titulos': autores_faltantes['autor_norm'].map(lambda x: titulos.get(x, [])),
            'ponente': True,
            'origen': 'Registro de ponencia'
        })
        p = pd.concat([p, extra], ignore_index=True)

    return p

@st.cache_data
def cargar_certificados():
    c = pd.read_csv(CERTIFICADOS, dtype=str).fillna('')
    c['nombre_norm'] = c['nombre'].map(normalizar)
    return c

certificados = cargar_certificados()

df = cargar()

st.markdown('''
<style>
.block-container {max-width: 900px; padding-top: 2rem;}
.hero {padding: 1.15rem 1.5rem; border: 2px solid #0b314f; border-radius: 18px; margin: .8rem 0 1rem; background: linear-gradient(135deg,#fffaf0,#ffffff);}
.hero h2 {color:#0b314f;margin-bottom:.25rem;}
.hero p {color:#167c80;margin:0;font-weight:600;}
.stTextInput input {border:2px solid #167c80 !important;border-radius:12px !important;}
.ficha h3 {color:#0b314f;}
[data-testid="stAlert"] {border-radius:12px;}
.badge-si {display:inline-block;padding:.35rem .7rem;border-radius:999px;background:#e8f5e9;color:#1b5e20;font-weight:700;}
.badge-no {display:inline-block;padding:.35rem .7rem;border-radius:999px;background:#f3f4f6;color:#374151;font-weight:700;}
.ficha {padding:1.1rem 1.25rem;border:1px solid rgba(128,128,128,.25);border-radius:16px;margin-top:.8rem;}
</style>
''', unsafe_allow_html=True)

st.image(str(LOGO), use_container_width=True)
st.markdown('<div class="hero"><h2>Consulta de inscritos</h2><p>III Congreso Colombiano de Etnomatemática · Riohacha, La Guajira</p></div>', unsafe_allow_html=True)

st.subheader('Consultar y descargar certificados de ponencia')
st.caption('Busca por nombre del autor o coautor. También puedes usar identificación si coincide con la inscripción registrada.')
consulta = st.text_input('Nombre o número de identificación', placeholder='Ej.: Juan Ignacio Hernández o 123456789')

if consulta.strip():
    qn = normalizar(consulta)
    qi = id_limpia(consulta)
    solo_digitos = bool(re.fullmatch(r'[\d\.\-\s]+', consulta.strip()))
    if solo_digitos:
        personas = df[df['id_norm'].eq(qi) & df['id_norm'].ne('')]
        nombres = set(personas['nombre_norm'])
        resultados = certificados[certificados['nombre_norm'].isin(nombres)]
    else:
        tokens = qn.split()
        resultados = certificados[certificados['nombre_norm'].map(lambda n: all(t in n.split() for t in tokens))]
    if resultados.empty:
        st.warning('No se encontraron certificados con ese dato. Intenta escribir solo el nombre o un apellido. Si buscas por identificación, es posible que el autor no la haya registrado.')
    else:
        st.success(f'Se encontraron {len(resultados)} certificado(s).')
        for _, r in resultados.iterrows():
            with st.container(border=True):
                st.markdown(f"**{r['nombre']}**")
                st.caption(r['codigo_certificado'])
                st.write('**Ponencia:**', r['titulo_ponencia'])
                st.link_button('📄 Abrir certificado PDF en Google Drive', r['enlace'], use_container_width=True)
else:
    st.info('Escribe el nombre o identificación para consultar los certificados.')

st.divider()
st.caption('III Congreso Colombiano de Etnomatemática · Certificados almacenados en Google Drive. La disponibilidad depende de los permisos de cada PDF.')
