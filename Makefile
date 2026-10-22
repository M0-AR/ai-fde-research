SHELL := /bin/bash
PYTHON ?= python3
export PYTHONPATH := src
MODEL ?= qwen2.5-1.5b

.PHONY: help setup tasks market benchmark benchmark-8b guardrail deployment cost stats figures report verify test lint all clean paper

help:
	@echo "FDE research pipeline"
	@echo "  make setup        install the package in editable mode"
	@echo "  make tasks        regenerate and self-validate the 48-task bank"
	@echo "  make market       collect live postings and analyze them"
	@echo "  make benchmark    run the full benchmark with MODEL=$(MODEL)"
	@echo "  make guardrail    train and evaluate the injection detector"
	@echo "  make deployment   run canonical and generated Compose stacks"
	@echo "  make cost         price the governed pipeline"
	@echo "  make stats        compute intervals and paired tests"
	@echo "  make figures      render publication figures"
	@echo "  make report       generate README.md and LaTeX numbers"
	@echo "  make verify       check result completeness and consistency"
	@echo "  make test         run the test suite"
	@echo "  make all          tasks, analyses, figures, report"

setup:
	$(PYTHON) -m pip install -e ".[dev]"

tasks:
	$(PYTHON) -m fde_research.tasks

market:
	$(PYTHON) -m fde_research.collect_jobs
	$(PYTHON) -m fde_research.analyze_market

benchmark:
	$(PYTHON) -m fde_research.benchmark --models $(MODEL)

benchmark-8b:
	$(PYTHON) -m fde_research.benchmark --models qwen3vl-8b

guardrail:
	$(PYTHON) -m fde_research.guardrail_eval

deployment:
	$(PYTHON) -m fde_research.deployment_eval --source both

cost:
	$(PYTHON) -m fde_research.cost_model

stats:
	$(PYTHON) -m fde_research.stats

figures:
	$(PYTHON) -m fde_research.figures

report:
	$(PYTHON) -m fde_research.report

verify:
	$(PYTHON) -m fde_research.verify_results

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests

all: tasks market guardrail deployment cost stats figures report verify

paper:
	@command -v pdflatex >/dev/null || { echo "pdflatex not installed; paper sources are in paper/"; exit 1; }
	cd paper && pdflatex -interaction=nonstopmode main.tex && bibtex main && pdflatex -interaction=nonstopmode main.tex && pdflatex -interaction=nonstopmode main.tex

clean:
	rm -rf .pytest_cache src/fde_research/__pycache__ tests/__pycache__
	rm -rf results/deployments
