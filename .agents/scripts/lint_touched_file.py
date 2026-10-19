import runpy; from pathlib import Path; script = Path(__file__).resolve().parent.parent.parent / 'scripts' / 'lint_touched_file.py'; runpy.run_path(str(script), run_name='__main__')
