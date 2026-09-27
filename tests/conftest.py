import sys
from pathlib import Path

# collector/ 안의 모듈을 그대로 import 할 수 있게
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "collector"))
