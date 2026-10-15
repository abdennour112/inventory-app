"""Print comparable data fingerprints without displaying credentials or hashes."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import connect
from psycopg import sql
with connect() as db:
    for table in ('categories','products','movements'):
        row=db.execute(sql.SQL("SELECT count(*) AS n,md5(COALESCE(string_agg(row_to_json(t)::text,'' ORDER BY id),'')) AS digest FROM {} t").format(sql.Identifier(table))).fetchone()
        print(table,row['n'],row['digest'])
