# pg_raw.py

# pip install psycopg2-binary

import psycopg2
conn = psycopg2.connect("host=9qasp5v56q8ckkf5dc.leapcellpool.com port=6438 dbname=fwnevukuwnfmddnaqado user=shnphrmibfubvrdjmryz password=ckbtxthnyevggmerzqnpuceknilbim sslmode=require")
cur = conn.cursor()
cur.execute("SET search_path TO my_schema")
cur.execute("CREATE TABLE IF NOT EXISTS test (id SERIAL PRIMARY KEY, name TEXT)")
cur.execute("INSERT INTO test (name) VALUES ('Raw')")
cur.execute("SELECT * FROM test")
print(cur.fetchall())
conn.commit()
cur.close()
conn.close()
