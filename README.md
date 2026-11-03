# TELARAÑA — Finanzas personales

Aplicación de escritorio (Windows) con interfaz oscura para llevar ingresos, obligaciones,
historial, rachas, proyección y objetivos de ahorro. Todo se guarda en tu equipo.

## Usar la aplicación (sin instalar Python)

1. Ve a **Releases** en este repositorio y descarga `TELARANA-Windows.zip`.
2. Descomprímelo y abre `TELARANA.exe`.

Tus datos se guardan en `%APPDATA%\TELARANA` (base de datos y ajustes), por lo que
actualizar la aplicación no borra nada.

> Windows Defender o SmartScreen pueden advertir sobre programas sin firma digital.
> Es una advertencia habitual en aplicaciones nuevas hechas con PyInstaller.

## Ejecutar desde el código

Requiere Python 3.10 o superior.

```
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Los datos se guardan siempre en `%APPDATA%\TELARANA`, fuera de la carpeta del programa. Si venías de una versión anterior, tu `data/telarana.db` se copia solo la primera vez.

## Publicar una nueva versión

1. Sube el número en `telarana/__init__.py`.
2. Crea y sube una etiqueta: `git tag v1.0.0 && git push origin v1.0.0`.
3. GitHub compila la app en Windows (pestaña **Actions**) y adjunta el `.zip` a **Releases**.

También puedes lanzar la compilación a mano desde **Actions → Compilar TELARAÑA para Windows → Run workflow**.

## Funciones

- Inicio con anillo de estado, racha en días, alertas y accesos rápidos.
- Ingresos y obligaciones (recurrentes y puntuales), con formularios dentro de la página.
- Historial con gráfica de 12 meses, Rachas, Proyección y Objetivos de ahorro.
- Configuración: umbral de alerta, símbolo de moneda, animaciones y barra lateral.
