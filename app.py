import streamlit as st
import pandas as pd
import re
import unicodedata
import hashlib
from pathlib import Path

st.set_page_config(page_title='Consulta de inscritos | III CCE', page_icon='🔎', layout='centered')

BASE = Path(__file__).parent
PARTICIPANTES = BASE / 'participantes.xlsx'
PONENCIAS = BASE / 'ponencias.xlsx'
LOGO = BASE / 'logo_congreso.jpg'
INDICE_CERTIFICADOS = BASE / 'certificados_index.csv'
CARPETA_CERTIFICADOS = BASE / 'certificados'


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

consulta = st.text_input('Número de identificación o nombre', placeholder='Ej.: 1144208484 o María del Mar Gómez')

if consulta.strip():
    qn = normalizar(consulta)
    qi = id_limpia(consulta)
    solo_digitos = bool(re.fullmatch(r'[\d\.\-\s]+', consulta.strip()))
    if solo_digitos:
        res = df[df['id_norm'] == qi]
    else:
        # Todas las palabras ingresadas deben estar presentes; funciona con orden parcial.
        tokens = [t for t in qn.split() if t]
        mask = df['nombre_norm'].map(lambda n: all(t in n.split() for t in tokens))
        res = df[mask]

    if res.empty:
        st.warning('No se encontró una persona con ese dato. Verifica la identificación o intenta con una parte del nombre.')
    else:
        st.caption(f'{len(res)} resultado(s) encontrado(s)')
        for _, r in res.iterrows():
            n1, n2, a1, a2 = dividir_nombre(r['nombre_completo'])
            st.markdown('<div class="ficha">', unsafe_allow_html=True)
            st.subheader(str(r['nombre_completo']).strip())
            c1, c2 = st.columns(2)
            with c1:
                st.write('**Identificación:**', id_limpia(r['identificacion']) or 'No registrada en el formulario de participación')
                st.write('**Primer nombre:**', n1 or '—')
                st.write('**Segundo nombre:**', n2 or '—')
            with c2:
                st.write('**Primer apellido:**', a1 or '—')
                st.write('**Segundo apellido:**', a2 or '—')
                estado = '<span class="badge-si">PONENTE</span>' if r['ponente'] else '<span class="badge-no">NO PONENTE</span>'
                st.markdown('**Participación:** ' + estado, unsafe_allow_html=True)
            if r['ponente']:
                st.markdown('**Título de la ponencia:**')
                for titulo in r['titulos']:
                    st.info(titulo)
            st.markdown('</div>', unsafe_allow_html=True)
else:
    st.info('Escribe una identificación o parte del nombre para iniciar la consulta.')

st.divider()
st.caption('Base de consulta del III Congreso Colombiano de Etnomatemática · Los datos se leen de los archivos oficiales incluidos en la aplicación.')


st.divider()
st.header('Descarga de certificados de ponencia')
st.write('Para autores y coautores de las 33 ponencias sustentadas el 7 de octubre de 2026.')
st.caption('Ingresa el código individual que te entregó la organización. No se requiere publicar tu identificación.')
codigo = st.text_input('Código individual de descarga', type='password', key='codigo_certificado')
if codigo.strip():
    if not INDICE_CERTIFICADOS.is_file():
        st.error('La base de certificados todavía no está disponible.')
    else:
        indice = pd.read_csv(INDICE_CERTIFICADOS, dtype=str).fillna('')
        digest = hashlib.sha256(codigo.strip().encode('utf-8')).hexdigest()
        encontrados = indice[indice['codigo_hash'] == digest]
        if encontrados.empty:
            st.warning('Código no encontrado. Comprueba el código enviado por la organización.')
        else:
            for _, cert in encontrados.iterrows():
                st.success(f"Certificado disponible: {cert['nombre']}")
                st.write('**Ponencia:**', cert['titulo'])
                nombre_archivo = Path(cert['archivo']).name
                ruta = CARPETA_CERTIFICADOS / nombre_archivo
                if ruta.is_file():
                    st.download_button(
                        'Descargar mi certificado (PDF)',
                        data=ruta.read_bytes(),
                        file_name=nombre_archivo,
                        mime='application/pdf',
                        key=f"descarga_{cert['id']}"
                    )
                else:
                    st.error('El PDF de este certificado no está disponible. Contacta a la organización.')
