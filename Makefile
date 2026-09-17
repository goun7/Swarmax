.PHONY: test perf demo schema seed seal drill otlp console ch-mirror cold-archive cold-verify dogfood-demo pdf scale-gate-ch trust-drill serve clean

test:
	python -m pytest tests -v

perf:
	python -m pytest tests/test_performance.py -v

demo:
	python demo.py

schema:
	python -c "from swarmax.db import connect, init_db_with_migrations; import tempfile, os; \
p = os.path.join(tempfile.mkdtemp(), 'swx.db'); c = connect(p); init_db_with_migrations(c); \
print('schema v', c.execute('SELECT MAX(version) FROM schema_version').fetchone()[0], '->', p)"

seed:
	python scripts/seed_fleet.py --reset

seal:
	python -c "import sys; sys.path.insert(0, 'src'); \
from swarmax.db import connect, init_db_with_migrations; from swarmax.sealing import load_or_create_seed, seal_ledger; \
import os, pathlib; p = os.environ.get('SWX_DB', 'data/swarmax.db'); \
pathlib.Path(p).parent.mkdir(parents=True, exist_ok=True); \
c = connect(p); init_db_with_migrations(c); print(seal_ledger(c, load_or_create_seed()))"

drill:
	python scripts/exit_drill.py --db $${SWX_DB:-data/swarmax.db} --seed-if-missing

compliance-drill:
	python scripts/compliance_drill.py --db $${SWX_DB:-data/swarmax.db}

dpo-report:
	python -c "import sys; sys.path.insert(0, 'src'); \
from swarmax.db import connect, init_db_with_migrations; from swarmax.dpo import DpoReport; \
import os; p = os.environ.get('SWX_DB', 'data/swarmax.db'); \
c = connect(p); init_db_with_migrations(c); print(DpoReport(c).render())"

otlp:
	python -m swarmax.otlp

pdf:
	python scripts/build_pdf_package.py

console: seed
	python -m swarmax.console --db data/swarmax.db \
	--admin-user "$${SWARMAX_ADMIN:-admin}" --admin-password "$${SWARMAX_ADMIN_PASSWORD:?set SWARMAX_ADMIN_PASSWORD (min 12 chars)}"

ch-mirror:
	python -c "import sys; sys.path.insert(0, 'src'); \
from swarmax.db import connect, init_db_with_migrations; from swarmax.ch import mirror_events_safe; \
import os; p = os.environ.get('SWX_DB', 'data/swarmax.db'); \
c = connect(p); init_db_with_migrations(c); \
r = mirror_events_safe(c); print(r); assert r.get('mirrored', 0) >= 0 and not r.get('degraded')"

# F3-scale gate against a real ClickHouse (§10.1). Env: SWARMAX_CH_URL,
# SWARMAX_CH_PASSWORD, optional SWARMAX_SCALE_ROWS (default 10M).
scale-gate-ch:
	python scripts/scale_gate_ch.py

# Evidence Trust Services T3.1: live RFC 3161 countersign drill against the
# real FreeTSA service (network required). Env: SWARMAX_TSA_URL to override.
trust-drill:
	python scripts/trust_drill.py

clean:
	rm -rf .pytest_cache **/__pycache__ demo.db

# B1 cold tier (§10.3): archive the evidence ledger to any S3-compatible store.
# Env: SWARMAX_S3_ENDPOINT, SWARMAX_S3_BUCKET, SWARMAX_S3_KEY, SWARMAX_S3_SECRET
cold-archive:
	python -c "import sys, os; sys.path.insert(0, 'src'); \
from swarmax.db import connect, init_db_with_migrations; from swarmax.coldstore import S3CompatStore, archive_ledger; \
c = connect(os.environ.get('SWX_DB', 'data/swarmax.db')); init_db_with_migrations(c); \
s = S3CompatStore(os.environ['SWARMAX_S3_ENDPOINT'], os.environ['SWARMAX_S3_BUCKET'], \
os.environ['SWARMAX_S3_KEY'], os.environ['SWARMAX_S3_SECRET']); \
print(archive_ledger(c, s))"

cold-verify:
	python -c "import sys, os; sys.path.insert(0, 'src'); \
from swarmax.coldstore import S3CompatStore, verify_archive; \
s = S3CompatStore(os.environ['SWARMAX_S3_ENDPOINT'], os.environ['SWARMAX_S3_BUCKET'], \
os.environ['SWARMAX_S3_KEY'], os.environ['SWARMAX_S3_SECRET']); \
r = verify_archive(s); print(r); assert r['ok']"

dogfood-demo:
	python scripts/dogfood/run_week1.py --reset
