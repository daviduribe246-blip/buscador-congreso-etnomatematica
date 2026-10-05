# Buscador de inscritos – III Congreso Colombiano de Etnomatemática

Aplicación Streamlit para consultar inscritos por identificación o nombre y verificar si son ponentes.

## Archivos
- `app.py`: aplicación.
- `participantes.xlsx`: base de inscritos.
- `ponencias.xlsx`: base de ponencias.
- `requirements.txt`: dependencias.

## Ejecutar localmente
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Publicar en Streamlit Community Cloud
Sube estos cuatro archivos a un repositorio de GitHub. En Streamlit Community Cloud selecciona el repositorio y usa `app.py` como archivo principal.

## Nota sobre nombres
Los Excel originales contienen el nombre completo en una sola columna. La separación en primer/segundo nombre y apellidos se hace mediante una heurística. La aplicación conserva y muestra siempre el nombre completo original como referencia.
