# SpiderFinance — Finanzas personales

Aplicación de escritorio (Windows) con interfaz oscura para llevar ingresos, obligaciones,
historial, rachas, proyección y objetivos de ahorro. Todo se guarda en tu equipo.

## Usar la aplicación (sin instalar Python)

1. Ve a **Releases** en este repositorio y descarga `SpiderFinance-Setup.exe`.
2. Ejecútalo: instala SpiderFinance en `C:\Program Files (x86)\SpiderFinance` y crea los accesos directos. También hay un `SpiderFinance-Portable.zip` que se usa sin instalar.

Tus datos se guardan en `%APPDATA%\SpiderFinance` (base de datos y ajustes), por lo que
actualizar la aplicación no borra nada.

> Windows Defender o SmartScreen pueden advertir sobre programas sin firma digital.
> Es una advertencia habitual en aplicaciones nuevas hechas con PyInstaller.

## Versión para celular

La carpeta `movil/` es una app web instalable (PWA) con las mismas secciones. Se publica sola en
GitHub Pages: abre `https://nilsonlopezdev.github.io/SpiderFinance/` en el celular y usa
**Agregar a pantalla de inicio** (Chrome: menú ⋮ → *Instalar app*; iPhone: Compartir → *Añadir a pantalla de inicio*).
Funciona sin internet. Los datos se guardan solo en el navegador de ese teléfono y no se sincronizan con el PC.

## Ejecutar desde el código

Requiere Python 3.10 o superior.

```
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Los datos se guardan siempre en `%APPDATA%\SpiderFinance`, fuera de la carpeta del programa. Si venías de una versión anterior, tu `data/telarana.db` se copia solo la primera vez.

## Publicar una nueva versión

1. Sube el número en `telarana/__init__.py`.
2. Crea y sube una etiqueta: `git tag v1.0.0 && git push origin v1.0.0`.
3. GitHub compila la app en Windows (pestaña **Actions**) y adjunta el `.zip` a **Releases**.

También puedes lanzar la compilación a mano desde **Actions → Compilar SpiderFinance para Windows → Run workflow**.

## Funciones

- Inicio con anillo de estado, racha en días, alertas y accesos rápidos.
- Ingresos y obligaciones (recurrentes y puntuales), con formularios dentro de la página.
- Historial con gráfica de 12 meses, Rachas, Proyección y Objetivos de ahorro.
- Configuración: umbral de alerta, símbolo de moneda, animaciones y barra lateral.
