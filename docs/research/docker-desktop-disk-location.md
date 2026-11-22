# Mover docker_data.vhdx a otra unidad (Docker Desktop 29.0.1, Windows, WSL2)

## Pregunta
¿Cuál es el método oficial y seguro para mover el disco de imagen de Docker Desktop (WSL2) a D: conservando contenedores y volúmenes?

## Respuesta
- Ruta por defecto: `%LOCALAPPDATA%\Docker\wsl\disk\docker_data.vhdx`. La documentación del backend WSL 2 indica cambiarla en Settings > Resources > Advanced (Disk image location).
- Docker documenta que mover el VHDX requiere el privileged helper y que no debe moverse a mano con el explorador de archivos (Docker pierde el rastro del archivo). Si el destino ya contiene una imagen, la UI pregunta si usar la existente o reemplazarla. ⚠ verificar en pantalla: la página de Settings cita esta opción solo para "Mac, Linux, Windows Hyper-V"; en 29.0.1 con WSL2 la opción puede aparecer o no.
- La documentación NO afirma que el cambio migre automáticamente contenedores/volúmenes existentes. ⚠ verificar en pantalla (mensaje de confirmación al cambiar la ruta).
- Clave en `%APPDATA%\Docker\settings-store.json`: NO aparece en docs.docker.com consultadas. Nombre y soporte de edición manual con Docker cerrado: no verificado. ⚠ verificar en pantalla (y comparar el JSON antes/después de cambiar la ruta por la UI; no inventar la clave).
- `wsl --export/--import`: no se menciona en docs.docker.com para las distros internas de Docker Desktop; no hay soporte documentado. Estado: no soportado/no documentado (la guía oficial de backup solo cita copiar `docker_data.vhdx` y respaldar distros WSL de usuario con la guía de Microsoft).
- Respaldo oficial previo: `docker container commit` + `docker image save` para imágenes; los volúmenes se respaldan aparte (guía de volúmenes); alternativa documentada: copiar `docker_data.vhdx` con Docker detenido.

## Decisión recomendada
1. Respaldar antes: `docker image save`/backup de volúmenes y copia del `docker_data.vhdx` con Docker Desktop cerrado (`wsl --shutdown`).
2. Cambiar la ruta solo desde Settings > Resources > Advanced > Disk image location (D:\...), aplicar y reiniciar. ⚠ verificar en pantalla que los contenedores/volúmenes siguen presentes (`docker ps -a`, `docker volume ls`).
3. No mover el archivo a mano, no editar `settings-store.json` ni usar `wsl --export/--import` sobre `docker-desktop` (sin respaldo oficial). Si la opción no aparece con WSL2, mantener la ruta por defecto y usar el respaldo del paso 1 como plan de restauración.

## Fuentes (consulta 2026-11-21)
- Docker Desktop WSL 2 backend on Windows — https://docs.docker.com/desktop/features/wsl/
- Change your Docker Desktop settings — https://docs.docker.com/desktop/settings-and-maintenance/settings/
- How to back up and restore your Docker Desktop data — https://docs.docker.com/desktop/settings-and-maintenance/backup-and-restore/
