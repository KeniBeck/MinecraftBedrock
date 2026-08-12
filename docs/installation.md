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
| `BEDROCK_PANEL_MONITORING_PROBE_HOST=` | (opcional) dirección que usa el backend para verificar el juego; en Docker, el gateway de la red (p. ej. `172.18.0.1`). Si no se define, usa `BEDROCK_PANEL_SERVER_PUBLIC_HOST`. |

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
> El backend corre en su propio contenedor y verifica el juego sondeándolo:
> ese sondeo no usa `BEDROCK_PANEL_SERVER_PUBLIC_HOST`, sino
> `BEDROCK_PANEL_MONITORING_PROBE_HOST` (en Docker, el gateway `172.18.0.1`),
> para que el estado pase a `running` aunque la IP LAN no sea alcanzable desde
> el contenedor.

---

## 10. Acceso remoto (opcional) — jugar con amigos fuera de tu red

Todo lo anterior te deja el panel funcionando en tu propia red (tu casa). Si
quieres que **amigos desde otra red** (otra casa, otro país) puedan entrar al
panel y/o jugar en tu servidor de Minecraft, hace falta un paso extra: un
**túnel**. Esto es opcional, gratis, y no requiere tocar el router.

> **Importante antes de empezar**: mientras uses esto, tu PC tiene que quedar
> prendida y con internet. Si la apagas o se corta tu conexión, el panel y el
> juego dejan de estar disponibles para tus amigos también. La calidad de la
> partida depende de tu internet — específicamente de tu **velocidad de
> subida**, no de la de bajada.

Son **dos cosas distintas** que se resuelven con **dos herramientas
distintas**:

| Qué quieres exponer | Herramienta | Por qué |
|---|---|---|
| El panel web (para administrar) | **Cloudflare Tunnel** | Gratis, sin límite de tiempo, pensada para tráfico web |
| El juego Bedrock en sí (para que jueguen) | **playit.gg** | Gratis, pensada específicamente para servidores de Minecraft |

Puedes usar solo una de las dos (por ejemplo, solo el juego, y administrar el
panel tú localmente) o ambas.

---

### 10.1. Exponer el panel — Cloudflare Tunnel

1. Descarga `cloudflared` para tu sistema desde
   https://github.com/cloudflare/cloudflared/releases/latest (elige el archivo
   que diga tu sistema: `windows-amd64.exe`, `darwin-amd64.tgz` para Mac,
   `linux-amd64.deb` para Ubuntu/Debian/Linux Mint).
2. Instálalo:
   - **Windows**: ejecuta el `.exe` descargado, o déjalo en una carpeta y
     úsalo desde ahí.
   - **macOS**: descomprime el `.tgz` y mueve el binario `cloudflared` a una
     carpeta de tu PATH (o córrelo desde donde quedó).
   - **Linux**: `sudo dpkg -i cloudflared-linux-amd64.deb`
3. Con el panel ya encendido (`docker compose ... up -d`), abre una terminal
   y ejecuta:

   ```bash
   cloudflared tunnel --url http://localhost:8080
   ```

   (cambia `8080` si usaste otro `BEDROCK_PANEL_HTTP_PORT`).

4. Verás en la terminal una línea con una URL parecida a:
   `https://palabras-random.trycloudflare.com` — **esa es la que les compartes
   a tus amigos** para entrar al panel. Funciona igual que `localhost:8080`,
   con login incluido.

> Esta URL cambia cada vez que cierras y vuelves a correr el comando. Sirve
> para uso ocasional. Si quieres una URL fija que no cambie, hace falta una
> cuenta gratuita de Cloudflare y un dominio propio — es un paso más
> avanzado, avísanos si lo necesitas y lo documentamos aparte.

**Seguridad**: en cuanto corras esto, cualquiera con esa URL puede llegar a la
pantalla de login de tu panel. Asegúrate de que la contraseña del
administrador (`BEDROCK_PANEL_BOOTSTRAP_ADMIN_PASSWORD`, paso 3 de esta guía)
sea larga y no la que viene de ejemplo.

---

### 10.2. Exponer el juego — playit.gg

1. Entra a https://playit.gg y crea una cuenta gratuita.
2. Descarga e instala el agente de playit para tu sistema:

   - **Windows**: descarga el instalador desde https://playit.gg/download y
     sigue el asistente — te pedirá vincular tu cuenta desde el navegador, es
     un solo clic.
   - **macOS**: igual que en Windows: descarga el instalador desde
     https://playit.gg/download y sigue el asistente.
   - **Linux**: el instalador oficial funciona en cualquier distro (Arch,
     Debian, Ubuntu, Fedora, openSUSE, Alpine) y detecta solo qué gestor de
     paquetes tienes:

     ```bash
     curl -fsSL https://packages.playit.gg/install.sh | bash
     ```

     > **Un tropiezo en Arch**: **no** uses `yay -S playit-gg` — ese nombre de
     > paquete no existe. El correcto en el AUR es `playit-bin`. El
     > instalador oficial de arriba instala `playit-bin` desde el AUR por ti
     > (usando `yay`/`paru` si los tienes); si prefieres hacerlo a mano:
     > `yay -S playit-bin`.

   - **Linux (después de instalar)**: `playit` corre como **servicio
     systemd** — ya está "corriendo", pero tu usuario común no puede hablar
     con él todavía. Si al ejecutar `playit` te aparece un error de socket
     restringido (`/run/playit/playitd.sock`), es justamente por esto. Se
     soluciona así:

     ```bash
     sudo usermod -aG playit $USER
     newgrp playit
     playit
     ```

     - El primer comando te agrega al grupo `playit` (pide tu contraseña).
     - `newgrp playit` aplica ese permiso en la terminal actual sin tener que
       cerrar sesión. Si no funciona, cierra la terminal y abre una nueva.
     - Recién ahí `playit` te va a mostrar el **claim code**.

3. Vincula el agente con tu cuenta (en Linux ya llegaste aquí con el claim
   code; en Windows/macOS el asistente lo hace solo):

   - Entra a https://playit.gg/account/setup/wizard/new-account/computer y
     elige "Your Computer" (no Docker ni Third Party App, salvo que corras el
     panel dentro de un contenedor Docker separado del agente).
   - La web te pedirá el **claim code** que te mostró `playit` en la
     terminal — pégalo ahí.
   - Una vez vinculado, la web mostrará tu agente como conectado (con la
     región/datacenter asignada automáticamente — normalmente no hace falta
     tocar esto).

4. En el panel de playit.gg, crea un túnel:

   - Tipo: **UDP**
   - Puerto local: `19132` (el puerto de Bedrock — revisa el puerto real del
     servidor que creaste desde BedrockPanel si usaste otro).

5. playit.gg te va a dar una dirección pública, algo como
   `algo.playit.gg:12345`. **Esa es la dirección que tus amigos ponen en
   Minecraft** (Agregar servidor → Dirección del servidor) para conectarse, en
   vez de tu IP local.

6. Si quieres que la dirección pública quede reflejada dentro del panel (para
   que se muestre correctamente a quien administre), pon esa misma dirección
   en `BEDROCK_PANEL_SERVER_PUBLIC_HOST` en tu `.env.prod` y reinicia:

   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```

---

### 10.3. Limitaciones de playit.gg (plan gratis)

Vale la pena conocerlas antes de prometerle disponibilidad a nadie:

| Limitación | Detalle |
|---|---|
| Cantidad de túneles | El plan gratis permite hasta 4 túneles TCP y 4 túneles UDP por cuenta |
| Dominio | La dirección pública es un subdominio random tipo `algo.ply.gg` — un dominio propio (`tudominio.com`) es solo del plan pago |
| Latencia agregada | El tráfico pasa por los servidores de playit, sumando entre 10 y 50 ms de ping extra sobre tu conexión directa |
| Bajo carga | En tráfico alto el plan gratis puede empezar a limitar/throttlear la velocidad |
| Depende de tu PC | El servidor sigue corriendo en tu máquina — si la apagas, se cae para todos, tenga o no túnel activo |
| Sin protección DDoS | El plan gratis no incluye protección contra ataques de denegación de servicio |
| Techo real de jugadores | No es un límite de playit en sí, sino de tu conexión: la mayoría de internet hogareño sostiene bien entre 5 y 10 jugadores simultáneos, por la subida disponible |

Ninguna de estas te impide arrancar — para un grupo chico de amigos, esto
sobra.

---

### 10.4. ¿Vale la pena para mi caso?

| Situación | ¿Recomendado? |
|---|---|
| Jugar con 2-4 amigos de forma ocasional | Sí, sin problema |
| Internet de casa con poca velocidad de subida | Funciona, pero puede haber lag con varios jugadores a la vez |
| Necesitas que esté disponible 24/7 de forma confiable | Esto depende de que tu PC quede prendida siempre — considera una PC/mini-servidor dedicado si es algo serio |
| Servidor con muchos jugadores simultáneos | El plan gratis de playit.gg puede quedarse corto — revisa sus límites actuales en su sitio |