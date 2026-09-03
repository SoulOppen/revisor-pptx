# Arquitectura — revisor-pptx

CLI en Python 3.12 con `uv`. Pipeline secuencial por archivo que nunca modifica
los originales: copiar → extraer texto → LanguageTool → filtrar de alta
confianza → aplicar a la copia → generar reporte markdown.

## Vista general del flujo

```
  <dir>  ──▶  copy_ppts  ──▶  extract_text  ──▶  revisar  ──▶  aplicar  ──▶  reporte
  (CLI)      copias en        (por slide)        (LT es)     (fix a la    (reporte
             corregidos/      shapes+tablas      │            copia)       markdown)
                              +notas             │                          ▲
                              │                  ▼                          │
                     lista[SlideText]      list[Correction]                 │
                                                │                           │
                                     ┌──────────▼──────────┐                │
                                     │ filter_corrections  │────────────────┘
                                     │ (función pura)      │
                                     └─────────────────────┘
```

## Módulos

| Módulo | Responsabilidad | Naturaleza |
|---|---|---|
| `revisor_pptx/main.py` | CLI + orquestación del pipeline | IO |
| `revisor_pptx/copy_ppts.py` | Copia segura de `.pptx` a `corregidos/` | IO |
| `revisor_pptx/extract_text.py` | Extracción de texto por slide | Pura + borde IO |
| `revisor_pptx/revisar.py` | Integración con LanguageTool + lifecycle | IO |
| `revisor_pptx/aplicar.py` | Filtro de confianza + aplicación de fixes | Pura + borde IO |
| `revisor_pptx/reporte.py` | Renderizado del reporte markdown | Pura |

## Límite puro ↔ IO

La regla de diseño es confinar el acceso a disco/red a los **bordes**, dejando la
lógica de negocio en **funciones puras** fácilmente testeables sin mocks.

| Función | Capa | Qué hace |
|---|---|---|
| `extract_slide_text(slide)` | Pura | Toma un objeto slide, devuelve `SlideText` |
| `extract_pptx(path)` | Borde IO | Abre el archivo, llama a la pura por slide |
| `filter_corrections(corrs)` | Pura | Decide qué correcciones aplicar |
| `generate_report(results)` | Pura | Renderiza markdown a partir de datos |
| `copy_directory(src, dest)` | Borde IO | Copia `.pptx` (shutil.copy2) |
| `apply_corrections(path, slides, corrs)` | Borde IO | Reabre la copia y la muta |
| `review_text(texts, lang)` | Borde IO | Llama a LanguageTool |
| `init_languagetool()` | Borde IO | Arranca el servidor/first-run download |

### Tipos de datos puros (`extract_text.py`, `reporte.py`)

- `TextSegment(text, offset, source)` — bloque de texto con su offset acumulado.
- `ShapeText(shape_idx, shape_name, segments)` — texto de una forma o grupo de celdas.
- `SlideText(slide_idx, shapes_text, notes)` — texto completo de una diapositiva.
- `Correction(...)` — un match de LanguageTool (`revisar.py`).
- `FileReport` / `SlideReport` / `ChangeDetail` — estructura del reporte.

## Estrategia de aplicación de correcciones

El modo más importante de la herramienta es **reemplazo por segmento/run**, para
preservar el formato (fuente, negrita, color) de los runs no afectados.

1. `review_text` devuelve `Correction`s con `offset`/`length` relativos al texto
   concatenado de cada forma.
2. `filter_corrections` (pura) conserva solo correcciones de alta confianza:
   - regla de tipo `misspelling`/`grammar`/`typo`, **y**
   - una sola reemplazo (auto-correct), o hasta 3 con longitud cercana a la original.
   - Excluye siempre `style`, `whitespace` y `casing`.
3. `apply_corrections` (IO) reabre la copia y, por offset acumulado, localiza el
   run exacto y reemplaza **solo el substring**, conservando el formato del run.
   - **Tablas**: misma lógica por celda (`cell.text_frame`).
   - **Notas del orador**: se aplican en `notes_text_frame`.

> **Nota de implementación (vs. diseño original):** `apply_corrections` recibe
> también `slides` (la lista de `SlideText` ya extraída) para mapear offsets a
> objetos de python-pptx, en lugar de volver a extraer dentro de la función. Es una
> mejora de eficiencia que no altera el contrato público del pipeline.

## LanguageTool

- **Servidor local** (preferido): requiere Java; sin límites de rate ni latencia de red.
- **Fallback a API pública**: se usa si Java no está disponible.
- **Lifecycle**: singleton a nivel de módulo, iniciado en `main()` y cerrado con `atexit`.

## Estrategia de testing

| Capa | Enfoque |
|---|---|
| Funciones puras | Pruebas unitarias sin IO (`filter_corrections`, `generate_report`, `extract_slide_text`) |
| Borde IO | Fixtures `.pptx` generados programáticamente en `conftest.py` |
| Integridad | Verificación de SHA-256 del original tras la copia y la corrección |

Los tests **nunca** usan archivos de usuario; todo se genera en `tmp_path`.
