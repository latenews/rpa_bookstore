import sys, os
sys.path.insert(0, '.')
from core.db_manager import DBManager
from config.settings import TEMPLATE_DIR

db = DBManager(TEMPLATE_DIR / 'master_db_template.xlsx')
df = db.load_all()
errors = db.validate(df)
print(f'오류 건수: {len(errors)}')
for e in errors:
    print(f'  행 {e["row"]}번 / 컬럼: {e["column"]} / {e["message"]}')
