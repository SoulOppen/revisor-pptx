# Guía de uso — revisor-pptx

Recorrido paso a paso para corregir presentaciones `.pptx` en español.

## 1. Preparación

### 1.1 Entorno

Se asume WSL (Ubuntu) con `uv` instalado y Python ≥ 3.12 disponible.

### 1.2 Instalar dependencias

```bash
cd revisor-pptx
uv sync
```

### 1.3 Verificar que funciona

```bash
uv run revisor-pptx --version
# revisor-pptx 0.1.0
```

## 2. Correr la corrección

### 2.1 Creá una carpeta con tus presentaciones

```
presentaciones/
├── charla.pptx
├── informe.pptx
└── notas.txt      # se ignora (no es .pptx)
```

### 2.2 Ejecutá el corrector

```bash
uv run revisor-pptx presentaciones
```

### 2.3 Resultado

```
presentaciones/
├── charla.pptx          # original intacto
├── informe.pptx         # original intacto
└── corregidos/
    ├── charla.pptx      # copia corregida
    ├── informe.pptx     # copia corregida
    └── reporte.md       # resumen de cambios
```

En la terminal verás una línea por archivo con el conteo de correcciones:

```
✓ charla.pptx: 3 corrección(es)
✓ informe.pptx: 1 corrección(es)
```

## 3. Leer el reporte

Abrí `corregidos/reporte.md`. Muestra cada cambio agrupado por archivo y diapositiva:

```markdown
# Reporte de correcciones

Se aplicaron **4** correcciones en **2** archivo(s).

## charla.pptx

### Diapositiva 1

| Original | Corregido | Otras opciones | Regla |
|---|---|---|---|
| munod | **mundo** | — | MORFOLOGIK_RULE_ES |
| una problema | **un problema** | uno | ... |
```

## 4. Comprobar el resultado

Abrí la copia en `corregidos/` con PowerPoint/LibreOffice para revisar visualmente
que el texto quedó correcto y que no se perdió formato.

## 5. Qué pasa en casos particulares

| Caso | Comportamiento |
|---|---|
| Carpeta vacía o sin `.pptx` | Imprime "No se encontraron archivos .pptx" y sale con código 0 |
| Archivo `.pptx` corrupto | Se salta ese archivo y continúa el lote |
| Sin acceso a internet / API caída | Avisa por archivo y deja la copia sin corregir; no corta el lote |
| Límite de solicitudes (429) | Reintenta automáticamente con backoff |

## Consejos

- Procesá primero una presentación de prueba chica antes de un lote grande.
- Los archivos se corrigen sobre la **copia**; borrá `corregidos/` cuando quieras
  volver a empezar desde los originales.
