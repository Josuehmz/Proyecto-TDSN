from __future__ import annotations

from sqlalchemy import select

from app.auth.security import hash_password
from app.db.models import Tenant, User
from app.db.session import session_scope
from app.ingest.pipeline import ingest_document
from app.logging_config import configure_logging, get_logger
from app.scripts.init_db import ensure_platform, ensure_tenant_schema


TENANTS = [
    {
        "slug": "acme",
        "name": "Acme Corp",
        "tier": "A",
        "users": [
            {
                "email": "admin@acme.test",
                "password": "Acme_Admin_2026!",
                "display_name": "Acme Admin",
                "roles": ["admin", "employee"],
                "clearance": "restricted",
                "departments": ["it"],
            },
            {
                "email": "legal@acme.test",
                "password": "Acme_Legal_2026!",
                "display_name": "Acme Legal",
                "roles": ["legal", "employee"],
                "clearance": "confidential",
                "departments": ["legal"],
            },
            {
                "email": "intern@acme.test",
                "password": "Acme_Intern_2026!",
                "display_name": "Acme Intern",
                "roles": ["employee"],
                "clearance": "public",
                "departments": ["marketing"],
            },
        ],
        "documents": [
            {
                "title": "Manual de onboarding Acme",
                "filename": "acme_onboarding.txt",
                "content": (
                    "Bienvenido a Acme Corp. Nuestra misión es construir cohetes "
                    "reutilizables para exploración planetaria. La oficina "
                    "principal está en Neo-Caldas. El código interno de proyecto "
                    "es BLUEFALCON-7. Horario flexible 9-18. La palabra clave "
                    "pública de Acme es QUASAR."
                ),
                "required_clearance": "public",
                "allowed_roles": [],
                "allowed_departments": [],
            },
            {
                "title": "Política de gastos Acme",
                "filename": "acme_gastos.txt",
                "content": (
                    "El tope diario por viáticos es COP 280.000. Comidas de "
                    "negocios hasta COP 150.000 por persona con aprobación. El "
                    "programa SUPERNOVA reembolsa el 100% de certificaciones "
                    "técnicas. Solo el equipo de Finanzas puede aprobar gastos "
                    "sobre COP 5.000.000."
                ),
                "required_clearance": "internal",
                "allowed_roles": [],
                "allowed_departments": [],
            },
            {
                "title": "Contrato confidencial Acme-Orion",
                "filename": "acme_contrato_orion.txt",
                "content": (
                    "Contrato OR-2026-09 firmado entre Acme Corp y Orion "
                    "Dynamics. Monto total USD 42.000.000 por el suministro de "
                    "propulsores de clase K. La cláusula SIGMA-9 permite "
                    "rescindir en 30 días por violación de exclusividad. Este "
                    "documento es CONFIDENCIAL y solo puede ser consultado por "
                    "el equipo legal de Acme."
                ),
                "required_clearance": "confidential",
                "allowed_roles": ["legal"],
                "allowed_departments": ["legal"],
            },
            {
                "title": "Política de teletrabajo y bienestar Acme",
                "filename": "acme_teletrabajo.txt",
                "content": (
                    "Los equipos de Acme pueden trabajar remoto hasta tres días por semana "
                    "con aprobación del líder. Las reuniones presenciales críticas tienen "
                    "prioridad los martes. Se facilita asesoría psicológica anónima vía "
                    "proveedor externo homologado. Contacto interno: people@acme.corp."
                ),
                "required_clearance": "public",
                "allowed_roles": [],
                "allowed_departments": [],
            },
            {
                "title": "Calendario corporativo Acme 2026",
                "filename": "acme_calendario_2026.txt",
                "content": (
                    "Cierre regional del 23 al 27 de diciembre 2026. Día de inventario "
                    "general el 14 de noviembre (sin operaciones en planta Neo-Caldas). "
                    "Asamblea anual de empleados en marzo; validar sede en intranet."
                ),
                "required_clearance": "public",
                "allowed_roles": [],
                "allowed_departments": [],
            },
            {
                "title": "Guía de comunicación y marca Acme",
                "filename": "acme_marca.txt",
                "content": (
                    "Usar siempre el logotipo aprobado en fondo claro u oscuro según manual "
                    "v3.2. En redes sociales, tono profesional y verificación legal previa "
                    "para cifras de mercado. Nunca atribuir partners sin contrato firmado."
                ),
                "required_clearance": "public",
                "allowed_roles": [],
                "allowed_departments": [],
            },
            {
                "title": "Procedimiento de gestión de accesos lógicos Acme",
                "filename": "acme_accesos_it.txt",
                "content": (
                    "Altas y bajas en IAM en un plazo máximo de 24 h hábiles. MFA "
                    "obligatorio para VPN y consolas de despliegue. Revocación automática "
                    "tras 90 días de inactividad en entornos no productivos. Auditoría "
                    "trimestral conjunta IT-Control Interno."
                ),
                "required_clearance": "internal",
                "allowed_roles": [],
                "allowed_departments": [],
            },
            {
                "title": "Estándar de respaldo y continuidad Acme",
                "filename": "acme_backup_bc.txt",
                "content": (
                    "Backups incrementales diarios y full semanal; retención mínima 35 días "
                    "en sitio y 180 días en nube cifrada. RTO objetivo 4 h para sistemas "
                    "críticos; RPO 1 h. Simulacro anual documentado ante la dirección."
                ),
                "required_clearance": "internal",
                "allowed_roles": [],
                "allowed_departments": [],
            },
            {
                "title": "Brief técnico propulsores clase K (uso interno)",
                "filename": "acme_propulsores_k.txt",
                "content": (
                    "Los propulsores clase K usan aleación revisada en 2025-Q4. Presión de "
                    "cámara nominal 9,2 MPa; ensayos destructivos solo en célula autorizada. "
                    "Cualquier modificación de geometría de inyector requiere CAB de "
                    "ingeniería y trazabilidad en JIRA-PROP."
                ),
                "required_clearance": "internal",
                "allowed_roles": [],
                "allowed_departments": [],
            },
            {
                "title": "Política de retención de datos y RGPD Acme",
                "filename": "acme_retencion_rgpd.txt",
                "content": (
                    "Datos de RR.HH. activos: conservación mientras dure la relación laboral "
                    "más 5 años según normativa local. Incidencias de seguridad: logs 24 "
                    "meses. Solicitudes de borrado: canal certificado sólo para personal "
                    "legal y DPO designado; registro obligatorio en libro de tratamientos."
                ),
                "required_clearance": "confidential",
                "allowed_roles": ["legal"],
                "allowed_departments": ["legal"],
            },
        ],
    },
    {
        "slug": "globex",
        "name": "Globex Industries",
        "tier": "A",
        "users": [
            {
                "email": "admin@globex.test",
                "password": "Globex_Admin_2026!",
                "display_name": "Globex Admin",
                "roles": ["admin", "employee"],
                "clearance": "restricted",
                "departments": ["it"],
            },
            {
                "email": "finance@globex.test",
                "password": "Globex_Fin_2026!",
                "display_name": "Globex Finance",
                "roles": ["finance", "employee"],
                "clearance": "confidential",
                "departments": ["finance"],
            },
            {
                "email": "employee@globex.test",
                "password": "Globex_Emp_2026!",
                "display_name": "Globex Employee",
                "roles": ["employee"],
                "clearance": "internal",
                "departments": ["operations"],
            },
        ],
        "documents": [
            {
                "title": "Catálogo público Globex 2026",
                "filename": "globex_catalogo.txt",
                "content": (
                    "Globex Industries fabrica robots de logística urbana. "
                    "Nuestro modelo insignia es el HELIOS-Mk3. El centro de "
                    "investigación está en Nueva Austral. La palabra clave "
                    "pública de Globex es NEBULA."
                ),
                "required_clearance": "public",
                "allowed_roles": [],
                "allowed_departments": [],
            },
            {
                "title": "Manual operativo interno Globex",
                "filename": "globex_operaciones.txt",
                "content": (
                    "La flota HELIOS debe recargarse cada 6 horas. El "
                    "protocolo RED-BASILISK activa la parada segura ante "
                    "fallas de batería. Los turnos son de 8 horas con descanso "
                    "obligatorio de 30 minutos."
                ),
                "required_clearance": "internal",
                "allowed_roles": [],
                "allowed_departments": [],
            },
            {
                "title": "Proyección financiera 2026 Globex",
                "filename": "globex_finanzas.txt",
                "content": (
                    "La proyección de ingresos 2026 de Globex es USD "
                    "180.000.000, con un margen EBITDA del 22%. Se reservan "
                    "USD 12.000.000 para adquisición de TITANIUM-WORKS. Este "
                    "documento es CONFIDENCIAL y solo puede consultarse por "
                    "el equipo financiero."
                ),
                "required_clearance": "confidential",
                "allowed_roles": ["finance"],
                "allowed_departments": ["finance"],
            },
            {
                "title": "Beneficios y salud Globex 2026",
                "filename": "globex_beneficios.txt",
                "content": (
                    "Programa dental y visual para familiares directos. Gimnasio con "
                    "convenio en sede Nueva Austral y cuatro ciudades aliadas. Chequeo "
                    "médico anual con perfil ampliado para personal de turnos nocturnos."
                ),
                "required_clearance": "public",
                "allowed_roles": [],
                "allowed_departments": [],
            },
            {
                "title": "Sostenibilidad y reciclaje de baterías Globex",
                "filename": "globex_sostenibilidad.txt",
                "content": (
                    "Meta 2027: 85% de baterías recuperadas de flota devueltas a refinería "
                    "certificada. Prohibido vertido en vertedero municipal. Reporte TRIM "
                    "de toneladas evitadas enviado a auditoría externa."
                ),
                "required_clearance": "public",
                "allowed_roles": [],
                "allowed_departments": [],
            },
            {
                "title": "Interacción urbana segura con robots Globex",
                "filename": "globex_urbana_publico.txt",
                "content": (
                    "Velocidad máxima en zonas peatonales 6 km/h. Distancia mínima 1,5 m "
                    "respecto a niños y mascotas. En caso de aglomeración, el operador "
                    "remoto puede asumir control en segundos; botón físico de parada en "
                    "cada unidad."
                ),
                "required_clearance": "public",
                "allowed_roles": [],
                "allowed_departments": [],
            },
            {
                "title": "Inspección pre-turno flota logística Globex",
                "filename": "globex_inspeccion_turno.txt",
                "content": (
                    "Lista de 14 puntos: integridad de bumpers, firmware del día, test de "
                    "frenado en seco y húmedo, estado LED de estado. Incidencia mayor: "
                    "retirar unidad y abrir ticket en OPS-LINE. Turnos de 8 h con registro "
                    "de firmas digitales."
                ),
                "required_clearance": "internal",
                "allowed_roles": [],
                "allowed_departments": [],
            },
            {
                "title": "Manual de calidad planta ensamble Globex",
                "filename": "globex_calidad_iso.txt",
                "content": (
                    "Auditorías internas ISO 9001 cada seis meses. Tolerancias de ensamble "
                    "según hoja MH-441; rechazo automático si desviación > 0,12 mm en "
                    "articulación principal. Herramientas de torque calibradas trimestralmente."
                ),
                "required_clearance": "internal",
                "allowed_roles": [],
                "allowed_departments": [],
            },
            {
                "title": "Plan de comunicación de crisis Globex",
                "filename": "globex_crisis_comms.txt",
                "content": (
                    "Comité de crisis: dirección, legal, operaciones y PRL. Respuesta "
                    "inicial pública en menos de 45 min. No confirmar cifras de víctimas "
                    "hasta validación de autoridades. Sala de guerra virtual permanente "
                    "en horario de incidente Nivel 2 o superior."
                ),
                "required_clearance": "internal",
                "allowed_roles": [],
                "allowed_departments": [],
            },
            {
                "title": "Memorando borrador — adquisición logística LATAM",
                "filename": "globex_memo_latam.txt",
                "content": (
                    "Evaluación preliminar de tres carriers regionales para consolidar "
                    "última milla en Chile y Perú. Capex estimado inicial USD 4,5 M; "
                    "payback proyectado 31 meses. Sujeto a due diligence y aprobación "
                    "del comité de inversiones. Distribución restringida a Finanzas."
                ),
                "required_clearance": "confidential",
                "allowed_roles": ["finance"],
                "allowed_departments": ["finance"],
            },
        ],
    },
]


def seed_demo() -> None:
    configure_logging()
    logger = get_logger(__name__)

    ensure_platform()

    for t_spec in TENANTS:
        slug = t_spec["slug"]
        with session_scope(None) as db:
            tenant = db.execute(select(Tenant).where(Tenant.slug == slug)).scalar_one_or_none()
            if tenant is None:
                tenant = Tenant(slug=slug, name=t_spec["name"], tier=t_spec["tier"])
                db.add(tenant)
                db.flush()
                logger.info("seed.tenant.created", slug=slug)

            for u in t_spec["users"]:
                existing = db.execute(
                    select(User).where(User.tenant_id == tenant.id, User.email == u["email"])
                ).scalar_one_or_none()
                if existing is not None:
                    continue
                db.add(
                    User(
                        tenant_id=tenant.id,
                        email=u["email"].lower(),
                        password_hash=hash_password(u["password"]),
                        display_name=u["display_name"],
                        roles=u["roles"],
                        clearance=u["clearance"],
                        departments=u["departments"],
                    )
                )
                logger.info("seed.user.created", tenant=slug, email=u["email"])

        ensure_tenant_schema(slug)

        with session_scope(slug) as db:
            from app.db.models import Document

            for d in t_spec["documents"]:
                exists = db.execute(
                    select(Document).where(Document.title == d["title"])
                ).scalar_one_or_none()
                if exists is not None:
                    continue
                ingest_document(
                    db,
                    title=d["title"],
                    filename=d["filename"],
                    content=d["content"].encode("utf-8"),
                    mime_type="text/plain",
                    required_clearance=d["required_clearance"],
                    allowed_roles=d["allowed_roles"],
                    allowed_departments=d["allowed_departments"],
                )

    logger.info("seed.done", tenants=[t["slug"] for t in TENANTS])


if __name__ == "__main__":
    seed_demo()
