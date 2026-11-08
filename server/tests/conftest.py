import sys
from pathlib import Path

# 让测试能直接 import app.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
