# 一键回归入口（只新增 eval 目标；既有 CI 不动，CI 仍照旧跑 pytest）
PYTHON ?= python3

.PHONY: eval test

eval:
	$(PYTHON) eval/run_cases.py
	cd engineering/memory-system && $(PYTHON) -m pytest tests/ -q -p no:cacheprovider

test: eval
