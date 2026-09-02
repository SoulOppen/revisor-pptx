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
|---|---|
| WSL (Ubuntu) | Entorno recomendado para correr el proyecto |
| [uv](https://docs.astral.sh/uv/) | Gestor de dependencias y entorno |
| Python ≥ 3.12 | Gestionado por uv |
| Java (opcional) | Solo para el servidor local de LanguageTool (ver abajo) |

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
2. Revisa el texto (formas, tablas y notas del orador) con LanguageTool en español.
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
| `2` | LanguageTool no disponible; los archivos quedan copiados sin corregir |

## Solución de problemas

| Problema | Qué hacer |
|---|---|
| **Java no está instalado** | La herramienta avisa y usa la API pública de LanguageTool en la nube (puede ser más lenta). Para el servidor local, instalá Java: `sudo apt install default-jre` |
| **Primera ejecución lenta** | La primera vez, el servidor local de LanguageTool se descarga e inicializa. Las siguientes corridas son más rápidas |
| **I/O lento en `/mnt/c/`** | Trabajar con archivos dentro de WSL (`~/` en lugar de `/mnt/c/...`) es sensiblemente más rápido que sobre el filesystem de Windows |

## Documentación

- [Guía de uso](docs/uso.md) — recorrido paso a paso.
- [Arquitectura](docs/arquitectura.md) — módulos, límites puro/IO y estrategia de aplicación.

## Licencia

MIT. Ver el archivo `LICENSE` (pendiente) para los términos completos.
