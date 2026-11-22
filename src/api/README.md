Servicio FastAPI (`create_app`) con `/health`, `buscar_solucion`, `consultar_estado_ticket` y `metricas_area`; el servidor MCP y `crear_ticket` llegan en T17 y T18.
Auth con `X-API-Key` (comparación en tiempo constante), errores JSON uniformes con `request_id`, límites de longitud y timeout por petición.
Los datos entran por inyección de dependencias (`ApiServices`): repositorio SQLite o Fabric y `AnswerService`; la API nunca indexa.
