# AGENTS.md — Instrucciones Globales y Reglas de Trabajo para el Agente AI

## 1. Visión General
Este repositorio contiene el panel de administración para servidores de Minecraft.
- **Frontend:** React + Vite + TypeScript + Tailwind CSS + Lucide Icons + TanStack Query + Vitest.
- **Backend:** FastAPI + Python (Modular Monolith / Clean Architecture).

---

## 2. Reglas de Trabajo del Agente
1. **Flujo Interactivo (Paso a Paso):** Implementar un módulo o tarea a la vez. NUNCA avanzar al siguiente bloque sin pedir y recibir confirmación explícita del usuario.
2. **Eficiencia y Ahorro de Tokens:**
   - Leer únicamente los archivos estrictamente necesarios para la tarea actual.
   - Evitar respuestas o explicaciones innecesariamente largas. Ir directo al código o la solución.
3. **TypeScript Estricto:**
   - Prohibido el uso de `any`.
   - Crear tipos e interfaces explícitas para respuestas de API y cargas de datos (DTOs).
4. **Gestión de Estado y Data Fetching:**
   - Toda llamada al backend debe organizarse mediante `@tanstack/react-query` usando hooks personalizados en `src/features/<modulo>/hooks.ts`.
5. **Control de Acceso (RBAC):**
   - Proteger componentes, botones y rutas según el nivel de permisos utilizando el hook `useCan('permiso.accion')`.

---

## 3. Configuración de Ejecución de Tests & Comandos (Salida Reducida)
Para evitar saturar la ventana de contexto con logs masivos:
- **Ejecución de Tests (Vitest):** Usar siempre `--reporter=dot` o silenciar la salida detallada para imprimir **únicamente errores y fallos**.
  - Ejemplo: `npx vitest run src/features/<modulo>/ --reporter=dot`
- **Diagnóstico:** Si los tests pasan, confirmar brevemente con el resultado. Si fallan, mostrar solo la traza de error (stack trace) relevante.

---

## 4. Estructura Estándar de Módulos (`src/features/`)
Todo nuevo módulo o feature en el frontend debe seguir la siguiente organización:

```text
src/
├── lib/api/<modulo>.ts         # Funciones de consumo directo de API (axios/fetch)
├── features/<modulo>/
│   ├── types.ts                # Tipos, interfaces y schemas del módulo
│   ├── hooks.ts                # Custom hooks (useQuery, useMutation)
│   ├── components/             # Componentes de UI, tablas, modales y formularios
│   ├── <Modulo>Page.tsx        # Componente vista/página principal
│   └── <modulo>.test.tsx       # Pruebas unitarias
└── routes/                     # Definición de rutas y protecciones