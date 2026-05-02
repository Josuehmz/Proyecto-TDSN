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
