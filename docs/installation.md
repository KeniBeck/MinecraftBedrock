# Instalación de BedrockPanel en Windows, macOS y Linux

Guía paso a paso **para cualquier PC** con Docker (sin tocar código). Al final
tendrás el panel corriendo en `http://localhost:8080` y podrás entrar con tu
usuario administrador sin escribir una sola línea de comandos de desplegado.

Si quieres los detalles técnicos de la pila, mira `docs/deployment.md`.

---

## 0. ¿Qué vas a obtener?

- La **base de datos** (Postgres) guardada en un volumen de Docker.
- El **panel** (frontend + backend) en una sola red privada.
- Un **administrador inicial** (`super_admin`) que se crea solo la primera vez,
  con el usuario y contraseña que tú definas.

Solo vas a necesitar **Docker**. El resto llega descargado automáticamente.

---

## 1. Instala Docker (elegir tu sistema)

### Windows
1. Instala **Docker Desktop** desde https://www.docker.com/products/docker-desktop/
2. Al instalar, marca **"Use WSL 2 instead of Hyper-V"** (recomendado).
3. Abre *Docker Desktop* y espera a que diga `Engine running`.

### macOS
1. Instala **Docker Desktop** (Apple silicon o Intel) desde el mismo enlace.
2. Abre *Docker Desktop* y acepta la instalación de los componentes adicionales
   cuando te lo pida.

### Linux — Ubuntu, Debian y derivadas (Linux Mint, Pop!_OS, Zorin…)

El instalador oficial de Docker **detecta tu distribución automáticamente** (apt,
dnf, pacman…), así que los pasos son los mismos en casi cualquier Linux. Las
derivadas de Debian/Ubuntu (como Linux Mint) están especialmente soportadas.

1. Instala Docker Engine y el plugin de Compose:

   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   ```

2. Para usar `docker` **sin sudo** (recomendado):

   ```bash
   sudo usermod -aG docker $USER
   # cierra sesión y vuelve a entrar (o reinicia el PC) para aplicar el grupo
   ```

3. Verifica:

   ```bash
   docker --version
   docker compose version
   ```

> Si prefieres repos oficiales en vez del script, crea el repo de tu distro en
> https://docs.docker.com/engine/install/ y elige tu sistema. El resto de esta
> guía es idéntico.

---

## 2. Consigue el proyecto

Descarga / descomprime / clona la carpeta de BedrockPanel en tu PC, por ejemplo:

```bash
git clone <URL-del-repositorio-o-pega-aqui-tu-copia> BedrockPanel
cd BedrockPanel
```

> En Windows: puedes usar el *Explorador de archivos* (botón derecho →
> *Extraer todo*). La carpeta elegida la llamaremos **la carpeta del panel**.

---

## 3. Crea tu archivo de configuración

Dentro de la carpeta del panel hay una plantilla llamada `.env.prod.example`.
Debes crear una copia llamada `.env.prod` y rellenar quién es el administrador.

En una terminal dentro de la carpeta del panel:

```bash
cp .env.prod.example .env.prod
```

> En Windows (PowerShell): `Copy-Item .env.prod.example .env.prod`

Abre `.env.prod` con el Bloc de notas / editor y revisa **al menos estos valores**:

| Variable | Qué poner |
|---|---|
| `POSTGRES_PASSWORD=` | una contraseña larga y segura para la base de datos |
| `BEDROCK_PANEL_IAM_ENCRYPTION_KEY=` | la clave Fernet (ver paso 4) |
| `BEDROCK_PANEL_BOOTSTRAP_ADMIN_USERNAME=` | el usuario administrador (p. ej. `admin`) |
| `BEDROCK_PANEL_BOOTSTRAP_ADMIN_PASSWORD=` | la contraseña con la que entrarás al panel |
| `BEDROCK_PANEL_SERVER_PUBLIC_HOST=` | `localhost` si juegas en este mismo PC |

> Las otras variables ya traen valores sensatos. No necesitas tocarlas.

---

## 4. Genera la clave Fernet (una sola vez)

Esta clave protege los secretos internos del panel (2FA, códigos de respaldo) y es
**obligatoria**. Es solo una cadena de texto: générela en el navegador:

Abre esta página y copia el texto que muestra **FernetKey**:

```
https://asecuritysite.com/encryption/fernet
```

Pégalo como valor de `BEDROCK_PANEL_IAM_ENCRYPTION_KEY` en tu `.env.prod`.

> **Guarda esta clave.** Si la pierdes y reinicias desde cero, se invalidarán los
> secretos antiguos. Con ella configurada ya no la necesitas a diario.

#### Clave de firma JWT (opcional pero recomendada)

Si dejas `BEDROCK_PANEL_IAM_JWT_SECRET` vacío, el panel usa una clave de desarrollo y
PyJWT muestra una advertencia (`InsecureKeyLengthWarning`). Para quitarla, genera una
cadena larga y pégala en esa variable:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Pega el resultado en `BEDROCK_PANEL_IAM_JWT_SECRET=`. No es obligatoria (el panel
funciona igual sin ella), solo silencia el aviso y es más seguro en producción.

---

## 5. Enciende el panel

Dentro de la carpeta del panel, ejecuta:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

La primera vez tarda unos minutos (descarga e instala todo). Verás algo como:
`Container bedrockpanel-frontend Started`, etc.

Cuando termine, abre el navegador en:

```
http://localhost:8080
```

> Si pusiste otro puerto en `BEDROCK_PANEL_HTTP_PORT`, úsalo en vez de `8080`.

---

## 6. Entra con tu administrador

En la pantalla de acceso usa el usuario y contraseña de
`BEDROCK_PANEL_BOOTSTRAP_ADMIN_USERNAME` / `BEDROCK_PANEL_BOOTSTRAP_ADMIN_PASSWORD`.
Ese usuario se crea automáticamente **la primera vez** que arranca el backend y
tiene permisos de **super_admin** (administrador total).

El administrador **no se crea dos veces**: si vuelves a encender el panel, se
mantiene tu usuario y sus datos.

---

## 7. Día a día

```bash
# ver el estado
docker compose -f docker-compose.prod.yml ps

# ver los registros del backend
docker compose -f docker-compose.prod.yml logs -f backend

# apagar (mantiene tus datos)
docker compose -f docker-compose.prod.yml stop

# encender de nuevo
docker compose -f docker-compose.prod.yml start

# mirar los logs del frontend (nginx)
docker compose -f docker-compose.prod.yml logs -f frontend
```

Tus datos importantes (mundo, backups, contenedores Minecraft) viven en la carpeta
que indiques con `BEDROCK_PANEL_STORAGE_ROOT` (por defecto
`/var/lib/bedrockpanel/instances`). Para **hacer copia de seguridad**: guarda esa
carpeta y, si quieres también la base de datos, vuelca el volumen de Postgres.

---

## 8. Solución de problemas

| Problema | Causa probable | Solución |
|---|---|---|
| `POSTGRES_PASSWORD` me da error aunque la puse | El volumen ya guardó una contraseña anterior | Borra el volumen y arranca de nuevo: `docker compose -f docker-compose.prod.yml down -v` y repite el paso 5. **¡Esto borra la DB actual!** |
| `http://localhost:8080` no carga | Docker Fanso / puerto ocupado | Revisa que Docker esté encendido (`Engine running`) y cambia `BEDROCK_PANEL_HTTP_PORT` a otro puerto (p. ej. `8081`), luego vuelve a `up -d --build`. |
| Error de `BEDROCK_PANEL_IAM_ENCRYPTION_KEY` | Falta la clave Fernet | Rellénala (paso 4) y vuelve a `up -d --build`. |
| El administrador no puede entrar | La contraseña de bootstrap cambió después de crearlo | El bootstrap solo crea el usuario **la primera vez**. Borra el volumen (`down -v`) o crea el usuario con el panel; si vas a repetir, hazlo **antes** de la primera arrancada. |
| Quiero empezar desde cero (todo limpio) | — | `docker compose -f docker-compose.prod.yml down -v`. **Destructivo**: borra DB y datos. |

---

## 9. Notas para jugar (Bedrock real)

El **panel** sirve en HTTP (TCP) en `localhost:8080`. El **juego** de Minecraft
Bedrock usa puertos **UDP `19132/19133`** a nivel de red en el contenedor del
servidor, que el panel gestiona a través del socket de Docker del host.
Si vas a exponerlo para jugar desde otras máquinas/red, abre también esos puertos
UDP según tu red y configura `BEDROCK_PANEL_SERVER_PUBLIC_HOST` con tu IP o DNS.