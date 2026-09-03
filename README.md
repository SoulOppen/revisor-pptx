# revisor-pptx

Corrector ortográfico y gramatical por lotes para presentaciones **.pptx** en español.

Ejecutá `uv run revisor-pptx <carpeta>` y la herramienta copia cada archivo a `corregidos/`,
corrige los errores de alta confianza en la **copia** y genera un reporte en Markdown.
**Los originales nunca se modifican.**

## Por qué copia en lugar de corregir el original

Tus `.pptx` originales no se tocan. Cada archivo se copia primero a `corregidos/` y **solo la
copia** se corrige. Si algo sale mal, perdés a lo sumo una copia corregida, nunca tu fuente.

## Requisitos

| Requisito | Detalle |
|---|---|---|
| WSL (Ubuntu) | Entorno recomendado para correr el proyecto |
| [uv](https://docs.astral.sh/uv/) | Gestor de dependencias y entorno |
| Python ≥ 3.12 | Gestionado por uv |
| Acceso a internet | La revisión llama a la **API pública de LanguageTool** en la nube |

## Motor de revisión

El corrector usa la **API pública de LanguageTool** (`https://api.languagetool.org/v2/check`) en español, sin Java, sin servidor local ni descargas grandes. Cada forma, celda de tabla y nota del orador se envía por separado a la API; los errores de alta confianza se aplican a la copia y el resto queda listado en el reporte para revisión humana.

## Instalación

```bash
cd revisor-pptx
uv sync
```

## Uso

```bash
uv run revisor-pptx <directorio>
```

Donde `<directorio>` es la carpeta que contiene los `.pptx` a corregir.

### Qué hace cada corrida

1. Copia cada `.pptx` a `<directorio>/corregidos/`.
2. Revisa el texto (formas, tablas y notas del orador) con la API de LanguageTool en español.
3. Aplica **solo** las correcciones de alta confianza a la copia.
4. Escribe el reporte en `corregidos/reporte.md` con cada cambio aplicado.

### Salida

```
<directorio>/
├── original.pptx          # ← intacto
└── corregidos/
    ├── original.pptx      # ← copia ya corregida
    └── reporte.md         # ← detalle de cada cambio
```

### Códigos de salida

| Código | Significado |
|---|---|
| `0` | Proceso correcto (aun sin correcciones) |
| `1` | Error de argumentos o directorio inválido |

## Solución de problemas

| Problema | Qué hacer |
|---|---|
| **Sin acceso a internet / API caída** | La herramienta avisa por archivo y deja la copia sin corregir; no corta el lote |
| **Muy lento con muchos textos** | La API pública tiene un límite de ~20 solicitudes/minuto; la herramienta reintenta con espera. Procesar lotes chicos o una presentación a la vez ayuda |
| **Rate limit (429)** | Se reintenta automáticamente con backoff; si persiste, esperá un momento antes de repetir |
| **I/O lento en `/mnt/c/`** | Trabajar con archivos dentro de WSL (`~/` en lugar de `/mnt/c/...`) es sensiblemente más rápido que sobre el filesystem de Windows |

## Documentación

- [Guía de uso](docs/uso.md) — recorrido paso a paso.
- [Arquitectura](docs/arquitectura.md) — módulos, límites puro/IO y estrategia de aplicación.

## Licencia

MIT. Ver el archivo `LICENSE` (pendiente) para los términos completos.
