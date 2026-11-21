"""Static catalog for the synthetic ticket generator (S3): branches, subcategories, texts.

Everything here is fictitious data for "Banco Altiplano". Cities are real Mexican cities;
branch names are ``"<city> NN"`` and carry no personal names. The 15 subcategories with
``has_kb=True`` match the knowledge base articles planned for T12; the rest have no
article (RN-06). Priority weights follow RN-01 (P1 branch/customer impact, P2 one user
cannot operate, P3 degradation with workaround, P4 request or question).
"""

from __future__ import annotations

from dataclasses import dataclass

METRO_CITIES: frozenset[str] = frozenset({"Ciudad de México", "Guadalajara", "Monterrey"})

# (city, state, region, number of branches). 40 metro + 80 foráneas = 120 branches.
CITIES: tuple[tuple[str, str, str, int], ...] = (
    ("Ciudad de México", "Ciudad de México", "Centro", 20),
    ("Guadalajara", "Jalisco", "Occidente", 10),
    ("Monterrey", "Nuevo León", "Noreste", 10),
    ("Puebla", "Puebla", "Centro", 5),
    ("Toluca", "Estado de México", "Centro", 3),
    ("Pachuca", "Hidalgo", "Centro", 1),
    ("Cuernavaca", "Morelos", "Centro", 2),
    ("Tlaxcala", "Tlaxcala", "Centro", 1),
    ("Querétaro", "Querétaro", "Bajío", 4),
    ("León", "Guanajuato", "Bajío", 4),
    ("Irapuato", "Guanajuato", "Bajío", 1),
    ("Celaya", "Guanajuato", "Bajío", 1),
    ("Aguascalientes", "Aguascalientes", "Bajío", 2),
    ("San Luis Potosí", "San Luis Potosí", "Bajío", 2),
    ("Zacatecas", "Zacatecas", "Bajío", 1),
    ("Morelia", "Michoacán", "Occidente", 2),
    ("Colima", "Colima", "Occidente", 1),
    ("Tepic", "Nayarit", "Occidente", 1),
    ("Puerto Vallarta", "Jalisco", "Occidente", 1),
    ("Mérida", "Yucatán", "Sureste", 4),
    ("Cancún", "Quintana Roo", "Sureste", 3),
    ("Chetumal", "Quintana Roo", "Sureste", 1),
    ("Villahermosa", "Tabasco", "Sureste", 2),
    ("Campeche", "Campeche", "Sureste", 1),
    ("Tuxtla Gutiérrez", "Chiapas", "Sur", 2),
    ("Oaxaca de Juárez", "Oaxaca", "Sur", 2),
    ("Acapulco", "Guerrero", "Sur", 2),
    ("Veracruz", "Veracruz", "Golfo", 2),
    ("Xalapa", "Veracruz", "Golfo", 1),
    ("Coatzacoalcos", "Veracruz", "Golfo", 1),
    ("Saltillo", "Coahuila", "Noreste", 2),
    ("Reynosa", "Tamaulipas", "Noreste", 2),
    ("Tampico", "Tamaulipas", "Noreste", 1),
    ("Nuevo Laredo", "Tamaulipas", "Noreste", 1),
    ("Chihuahua", "Chihuahua", "Norte", 2),
    ("Ciudad Juárez", "Chihuahua", "Norte", 3),
    ("Torreón", "Coahuila", "Norte", 2),
    ("Durango", "Durango", "Norte", 1),
    ("Tijuana", "Baja California", "Noroeste", 4),
    ("Mexicali", "Baja California", "Noroeste", 2),
    ("Hermosillo", "Sonora", "Noroeste", 2),
    ("Ciudad Obregón", "Sonora", "Noroeste", 1),
    ("Culiacán", "Sinaloa", "Noroeste", 2),
    ("Mazatlán", "Sinaloa", "Noroeste", 1),
    ("La Paz", "Baja California Sur", "Noroeste", 1),
)

# Branch areas of the requester, with relative weights.
AREAS: tuple[tuple[str, int], ...] = (
    ("Caja", 25),
    ("Ejecutivos de cuenta", 25),
    ("Crédito", 15),
    ("Operaciones", 15),
    ("Gerencia", 10),
    ("Cobranza", 10),
)

# Channel and relative weight.
CHANNELS: tuple[tuple[str, int], ...] = (
    ("portal", 35),
    ("correo", 25),
    ("teléfono", 25),
    ("Teams", 15),
)

ESCALATION_PREFIX: dict[str, str] = {"es": "Escalado a L2. ", "en": "Escalated to L2. "}


@dataclass(frozen=True)
class SubcategorySpec:
    """One ticket subcategory and how the generator draws its tickets."""

    name: str
    categoria: str
    weight: int  # relative frequency (weights sum to 100)
    priority_weights: tuple[int, int, int, int]  # P1, P2, P3, P4
    has_kb: bool
    repetitive: bool
    escalation_rate: float  # share of tickets escalated to L2
    solutions_es: tuple[str, ...]
    solutions_en: tuple[str, ...]
    areas: tuple[str, ...] = ()  # empty = any area


SUBCATEGORIES: tuple[SubcategorySpec, ...] = (
    # --- The 5 repetitive subcategories (40% of the weight) ---
    SubcategorySpec(
        "Reseteo de contraseña", "Accesos", 11, (0, 75, 20, 5), True, True, 0.0,
        ("Se validó la identidad del usuario con su número de empleado y se restableció la "
         "contraseña desde el portal de autoservicio.",
         "Se generó una contraseña temporal y se guió al usuario para definir una nueva que "
         "cumple la política de seguridad."),
        ("User identity was verified with the employee number and the password was reset "
         "through the self-service portal.",
         "A temporary password was issued and the user was guided to set a new one that "
         "meets the security policy."),
    ),
    SubcategorySpec(
        "Desbloqueo de usuario", "Accesos", 10, (0, 80, 15, 5), True, True, 0.0,
        ("La cuenta estaba bloqueada por intentos fallidos; se desbloqueó en el directorio "
         "activo y se confirmó el acceso.",
         "Una sesión antigua con credenciales vencidas bloqueaba la cuenta; se cerró la "
         "sesión y se desbloqueó el usuario."),
        ("The account was locked after failed sign-in attempts; it was unlocked in the "
         "directory and access was confirmed.",
         "An old session with expired credentials kept locking the account; the session was "
         "closed and the user was unlocked."),
    ),
    SubcategorySpec(
        "Token bancario", "Accesos", 7, (5, 65, 25, 5), True, True, 0.0,
        ("Se resincronizó el token bancario del usuario y se validó la generación de claves "
         "dinámicas.",
         "El token estaba vencido; se activó el token de reemplazo asignado a la sucursal."),
        ("The banking token was resynchronized and the dynamic codes were validated.",
         "The token had expired; the replacement token assigned to the branch was activated."),
    ),
    SubcategorySpec(
        "VPN", "Conectividad", 6, (0, 45, 50, 5), True, True, 0.0,
        ("Se reinstaló el perfil de VPN y se renovó el certificado del equipo.",
         "El cliente de VPN estaba desactualizado; se actualizó y se verificó la conexión."),
        ("The VPN profile was reinstalled and the device certificate was renewed.",
         "The VPN client was outdated; it was updated and the connection was verified."),
    ),
    SubcategorySpec(
        "Impresoras", "Hardware", 6, (0, 10, 70, 20), True, True, 0.0,
        ("Se limpió la cola de impresión y se reinstaló el controlador de la impresora.",
         "La impresora estaba fuera de línea por un cambio de IP; se reconfiguró el puerto."),
        ("The print queue was cleared and the printer driver was reinstalled.",
         "The printer was offline after an IP change; the port was reconfigured."),
    ),
    # --- Other subcategories with a KB article ---
    SubcategorySpec(
        "Acceso a SAP", "Accesos", 6, (0, 40, 45, 15), True, False, 0.10,
        ("Se asignó el rol de SAP del puesto y se confirmó el acceso a la transacción.",
         "Se restableció la contraseña de SAP y se limpió la caché de SAP GUI."),
        ("The SAP role for the job was assigned and access to the transaction was confirmed.",
         "The SAP password was reset and the SAP GUI cache was cleared."),
    ),
    SubcategorySpec(
        "Acceso a core bancario", "Accesos", 4, (25, 55, 20, 0), True, False, 0.25,
        ("Se reactivó el perfil en el core bancario tras validar la autorización del gerente.",
         "Se corrigió el horario de acceso del perfil en el core bancario."),
        ("The core banking profile was reactivated after the manager approval was validated.",
         "The access schedule of the core banking profile was corrected."),
    ),
    SubcategorySpec(
        "Carpetas compartidas", "Conectividad", 5, (0, 20, 55, 25), True, False, 0.05,
        ("Se agregó al usuario al grupo de la carpeta compartida y se mapeó la unidad de red.",
         "La unidad de red estaba desconectada; se reconectó y se validaron los permisos."),
        ("The user was added to the shared folder group and the network drive was mapped.",
         "The network drive was disconnected; it was reconnected and the permissions checked."),
    ),
    SubcategorySpec(
        "Equipo lento", "Hardware", 6, (0, 5, 65, 30), True, False, 0.10,
        ("Se liberó espacio en disco y se deshabilitaron programas de inicio innecesarios.",
         "El antivirus escaneaba en horario laboral; se reprogramó el escaneo."),
        ("Disk space was freed and the unnecessary startup programs were disabled.",
         "The antivirus was scanning during business hours; the scan was rescheduled."),
    ),
    SubcategorySpec(
        "Escáner de cheques", "Hardware", 3, (15, 60, 25, 0), True, False, 0.20,
        ("Se limpiaron los rodillos del escáner de cheques y se recalibró el lector.",
         "Se reinstaló el controlador del escáner de cheques y se digitalizó una prueba."),
        ("The check scanner rollers were cleaned and the reader was recalibrated.",
         "The check scanner driver was reinstalled and a test document was scanned."),
        ("Caja", "Operaciones"),
    ),
    SubcategorySpec(
        "Sistema de caja", "Hardware", 4, (70, 30, 0, 0), True, False, 1.0,  # RN-03
        ("Soporte de caja reinició el servicio de la terminal y se cuadró la operación.",
         "Se reemplazó la terminal de caja con equipo de respaldo y se validó la operación."),
        ("Teller support restarted the terminal service and the transaction was balanced.",
         "The teller terminal was replaced with backup equipment and the operation validated."),
        ("Caja", "Operaciones"),
    ),
    SubcategorySpec(
        "Correo", "Comunicaciones", 7, (0, 25, 55, 20), True, False, 0.05,
        ("Se reconstruyó el perfil de Outlook y se sincronizó el buzón.",
         "El buzón estaba lleno; se archivaron correos antiguos y se restableció la recepción."),
        ("The Outlook profile was rebuilt and the mailbox was synchronized.",
         "The mailbox was full; old emails were archived and the inbox works again."),
    ),
    SubcategorySpec(
        "Microsoft Teams", "Comunicaciones", 4, (0, 10, 60, 30), True, False, 0.05,
        ("Se limpió la caché de Teams y se reinstaló la aplicación.",
         "Se configuraron los permisos de micrófono y cámara y se probó una llamada."),
        ("The Teams cache was cleared and the app was reinstalled.",
         "Microphone and camera permissions were set and the user made a test call."),
    ),
    SubcategorySpec(
        "Telefonía", "Comunicaciones", 3, (5, 25, 55, 15), True, False, 0.15,
        ("Se reconfiguró la extensión del teléfono IP y se probaron llamadas.",
         "Se reemplazó el cable de red del teléfono IP y la extensión volvió a registrarse."),
        ("The IP phone extension was reconfigured and calls were tested.",
         "The IP phone network cable was replaced and the extension registered again."),
    ),
    SubcategorySpec(
        "Instalación de software", "Software", 4, (0, 0, 30, 70), True, False, 0.05,
        ("Se instaló el software autorizado desde el catálogo corporativo.",
         "Se instaló la actualización solicitada con privilegios de administrador."),
        ("The approved software was installed from the corporate catalog.",
         "The requested update was installed with administrator rights on the device."),
    ),
    # --- Subcategories without a KB article (RN-06) ---
    SubcategorySpec(
        "Alta de usuario", "Accesos", 4, (0, 0, 20, 80), False, False, 0.10,
        ("Se creó la cuenta del nuevo colaborador con los accesos del perfil de puesto.",
         "Se dieron de alta el correo y los accesos básicos según la solicitud aprobada."),
        ("The account of the new employee was created with the job profile access.",
         "Email and basic access were created as the approved request specified."),
    ),
    SubcategorySpec(
        "Red de sucursal", "Conectividad", 3, (60, 30, 10, 0), False, False, 0.60,
        ("Se reinició el equipo de comunicaciones y el proveedor restableció el enlace.",
         "Se conmutó la sucursal al enlace de respaldo mientras se reparaba el principal."),
        ("The branch network equipment was restarted and the carrier restored the link.",
         "The branch was switched to the backup link while the main link was repaired."),
    ),
    SubcategorySpec(
        "Equipo dañado", "Hardware", 3, (5, 35, 50, 10), False, False, 0.50,
        ("Se reemplazó el equipo dañado por uno de respaldo y se migró la información.",
         "El técnico en sitio cambió la fuente de poder y el equipo volvió a encender."),
        ("The damaged device was replaced with a backup unit and the data was migrated.",
         "The on-site technician replaced the power supply and the device powered on."),
    ),
    SubcategorySpec(
        "Sospecha de fraude", "Seguridad", 1, (90, 10, 0, 0), False, False, 1.0,  # RN-03
        ("Se bloquearon preventivamente las credenciales involucradas y se turnó el caso a "
         "Seguridad de la Información.",
         "Se preservó la evidencia del incidente y Seguridad de la Información tomó el caso."),
        ("The credentials involved were blocked and the case went to Information Security.",
         "The incident evidence was preserved and Information Security took the case."),
    ),
    SubcategorySpec(
        "Consulta general", "Solicitudes", 3, (0, 0, 20, 80), False, False, 0.0,
        ("Se resolvió la duda del usuario y se compartió la guía correspondiente.",
         "Se orientó al usuario sobre el procedimiento y se cerró la solicitud."),
        ("The question of the user was answered and the relevant guide was shared.",
         "The user was guided through the procedure and the request was closed."),
    ),
)  # fmt: skip

KB_SUBCATEGORIES: tuple[str, ...] = tuple(s.name for s in SUBCATEGORIES if s.has_kb)
REPETITIVE_SUBCATEGORIES: frozenset[str] = frozenset(s.name for s in SUBCATEGORIES if s.repetitive)
