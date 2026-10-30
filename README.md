# TELARAÑA — Finanzas personales

Versión de escritorio con interfaz oscura, tecnológica y minimalista.

## Cambios de esta versión

- Inicio rediseñado igual a la maqueta: cabecera con logo y selector de mes, tarjetas de ingresos y obligaciones a los lados, anillo central con la imagen de estado, racha en días, cuatro tarjetas inferiores clicables y panel reservado.
- **Barra lateral corregida**: ahora es compacta (solo íconos, con globo de ayuda al pasar el cursor) y se expande con el botón « para mostrar los nombres. Íconos dibujados por la propia app, sin depender de símbolos de fuentes. Se eliminó la animación de borde que la refrescaba 12 veces por segundo.
- **Imagen de estado corregida**: aro, progreso y foto circular se componen en una sola imagen, sin canvas superpuesto ni esquinas cuadradas. Se agregó `estado_sin_datos.png` (Spider-Man de esmoquin) para el estado "Sin datos" y se redujo el peso de `estado_falta_dinero.png` (2048 px → 800 px).
- La racha ahora se muestra en días y se activa con 3 meses consecutivos con el mismo resultado.
- Las alertas son reales: se avisa cuando las obligaciones superan los ingresos o usan el 90 % o más.
- Se mantienen todas las funciones existentes y la base de datos local en `data/`.

## Ejecutar

En Windows:

1. Ejecuta `INICIAR_TELARANA.bat`.
2. El lanzador crea `.venv` si no existe.
3. Instala `requirements.txt`.
4. Abre `main.py`.

También se puede ejecutar manualmente con el entorno virtual activado:

```text
python main.py
```

## Estructura

- `main.py` — interfaz y navegación.
- `telarana/database.py` — base SQLite y operaciones de datos.
- `telarana/finance.py` — cálculos financieros.
- `telarana/visuals.py` — íconos y anillo de estado (PIL).
- `assets/` — imágenes de estados y rachas.
- `data/` — base de datos local.
