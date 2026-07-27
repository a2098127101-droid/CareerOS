"""CareerOS v1.5 persistent Domain Intelligence.

Revision ID: 0009_domain_intelligence_v15
Revises: 0008_canonical_runtime_consistency
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009_domain_intelligence_v15"
down_revision = "0008_canonical_runtime_consistency"
branch_labels = None
depends_on = None

NEW_TABLES = [
    "evidence_item_verification_history",
    "capability_taxonomies",
    "capabilities",
    "capability_versions",
    "domain_claims",
    "domain_claim_versions",
    "claim_evidence_links",
    "claim_capability_links",
    "job_requirement_versions",
    "job_requirement_capability_links",
    "capability_assessments",
    "capability_assessment_evidence",
    "career_gaps",
    "career_gap_versions",
    "domain_audit_events",
]


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "evidence_items" in tables:
        cols = _columns("evidence_items")
        additions = [
            ("verification_status", sa.Column("verification_status", sa.Text(), nullable=False, server_default="SELF_REPORTED")),
            ("verification_method", sa.Column("verification_method", sa.Text(), nullable=False, server_default="")),
            ("verification_confidence", sa.Column("verification_confidence", sa.Float(), nullable=False, server_default="0")),
            ("verified_by", sa.Column("verified_by", sa.Text(), nullable=False, server_default="")),
            ("verified_at", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True)),
            ("source_hash", sa.Column("source_hash", sa.Text(), nullable=False, server_default="")),
        ]
        for name, column in additions:
            if name not in cols:
                op.add_column("evidence_items", column)
        op.execute("""UPDATE evidence_items SET verification_status=CASE WHEN COALESCE(verified,0)=1 THEN 'VERIFIED' ELSE 'SELF_REPORTED' END WHERE verification_status IS NULL OR verification_status=''""")

    if "job_requirements" in tables:
        cols = _columns("job_requirements")
        if "version" not in cols:
            op.add_column("job_requirements", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        if "updated_at" not in cols:
            op.add_column("job_requirements", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        op.execute("UPDATE job_requirements SET updated_at=COALESCE(updated_at,created_at,CURRENT_TIMESTAMP)")

    # The checked-in schema manifest is the single source for fresh installs. Reuse the same
    # SQLAlchemy tables here so upgrades from 0008 create precisely the v1.5 canonical tables.
    from app.core.database import BASELINE_METADATA
    for name in NEW_TABLES:
        table = BASELINE_METADATA.tables.get(name)
        if table is None:
            raise RuntimeError(f"v1.5 schema manifest missing table: {name}")
        table.create(bind=bind, checkfirst=True)

    op.execute("""INSERT INTO capability_taxonomies
        (taxonomy_id,tenant_id,name,description,version,status,created_by)
        SELECT 'TAX-CAREEROS-CORE-V1','global','CareerOS Core Capabilities',
               'Versioned baseline taxonomy for explainable career capability assessment.',1,'active','system'
        WHERE NOT EXISTS (SELECT 1 FROM capability_taxonomies WHERE taxonomy_id='TAX-CAREEROS-CORE-V1')""")
    seeds = [
        ("CAP-USER-RESEARCH","user_research","用户研究","research",'["用户访谈","访谈","需求调研","user research","interview"]'),
        ("CAP-REQUIREMENTS","requirements_analysis","需求分析","analysis",'["需求理解","需求分析","业务需求","requirements"]'),
        ("CAP-DATA-ANALYSIS","data_analysis","数据分析","analysis",'["数据分析","统计分析","问卷分析","data analysis","analytics"]'),
        ("CAP-SQL","sql","SQL与数据库","technical",'["sql","数据库","database"]'),
        ("CAP-PYTHON","python","Python","technical",'["python","pandas","numpy"]'),
        ("CAP-COMMUNICATION","communication","沟通表达","communication",'["沟通","表达","汇报","communication","presentation"]'),
        ("CAP-INSIGHT","insight_communication","洞察表达","communication",'["洞察","材料总结","分析报告","insight"]'),
        ("CAP-PROJECT","project_collaboration","项目协作","collaboration",'["项目协作","团队协作","项目管理","project","collaboration"]'),
        ("CAP-TOOLS","digital_tools","数字工具","technical",'["工具能力","excel","power bi","tableau","办公软件"]'),
        ("CAP-WRITING","professional_writing","专业写作","communication",'["写作","报告","文案","writing"]'),
    ]
    for cid, key, name, category, aliases in seeds:
        bind.execute(sa.text("""INSERT INTO capabilities
            (capability_id,tenant_id,taxonomy_id,capability_key,name,category,description,aliases_json,level_scale_json,version,status,created_by)
            SELECT :cid,'global','TAX-CAREEROS-CORE-V1',:key,:name,:category,'CareerOS core capability',:aliases,:scale,1,'active','system'
            WHERE NOT EXISTS (SELECT 1 FROM capabilities WHERE capability_id=:cid)"""),
            {"cid":cid,"key":key,"name":name,"category":category,"aliases":aliases,"scale":'{"min":0,"max":100}'})


def downgrade() -> None:
    # Preserve historical assessments/claims on downgrade. Removing first-class intelligence data is
    # intentionally not automatic; restore a pre-upgrade backup for a destructive rollback.
    pass
