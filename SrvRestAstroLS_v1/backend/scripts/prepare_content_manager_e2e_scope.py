#!/usr/bin/env python3
"""Create the isolated Content Manager DEV knowledge scope (explicit apply only)."""
from __future__ import annotations
import argparse, asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import get_settings
from psycopg import AsyncConnection

async def run(apply: bool) -> None:
    settings=get_settings()
    if settings.env != 'development' or not settings.content_manager_e2e_enabled:
        raise SystemExit('Explicit TEBAAI_CONTENT_MANAGER_E2E_ENABLED=true in DEV is required')
    conn=await AsyncConnection.connect(settings.postgres_resolved_dsn())
    try:
        cur=await conn.execute("""SELECT organization_id,workspace_id,project_id FROM knowledge_scopes
                                  WHERE knowledge_scope_code='breslov_primary' AND status='active'""")
        base=await cur.fetchone()
        if not base: raise SystemExit('breslov_primary tenant baseline not found')
        cur=await conn.execute("SELECT id FROM knowledge_scopes WHERE project_id=%s AND knowledge_scope_code=%s",
                               (base[2],settings.content_manager_e2e_scope))
        existing=await cur.fetchone()
        if not apply:
            print({'mode':'dry-run','would_create':not bool(existing),'scope':settings.content_manager_e2e_scope,
                   'collection':settings.content_manager_e2e_collection,'primary_modified':False})
            await conn.rollback(); return
        if not existing:
            await conn.execute("""INSERT INTO knowledge_scopes(
                organization_id,workspace_id,project_id,knowledge_scope_code,name,description,
                scope_type,language_policy,status,metadata)
                VALUES(%s,%s,%s,%s,'Content Manager E2E','Isolated DEV write-validation scope',
                'bibliographic_corpus','es,he','active',%s::jsonb)""",
                (*base,settings.content_manager_e2e_scope,
                 '{"content_manager_e2e":true,"primary_routing":false}'))
        await conn.commit()
        print({'mode':'apply','scope':settings.content_manager_e2e_scope,'created':not bool(existing),'primary_modified':False})
    finally: await conn.close()

def main():
    p=argparse.ArgumentParser(); p.add_argument('--apply',action='store_true'); a=p.parse_args()
    asyncio.run(run(a.apply))
if __name__=='__main__': main()
