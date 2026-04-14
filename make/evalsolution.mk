# ---------------------------------------------------------------------------
# evalsolution.mk — evaluate, test, and score the tt-translated project
#
# This file contains the main iteration loop for developing the translation
# tool (tt).  Use evaluate_tt for the full end-to-end check; use the
# individual spinup/translate targets for faster feedback during development.
#
# Port used by the translated project: 3335 (set PYTX_PORT to override)
# ---------------------------------------------------------------------------
.PHONY: evaluate test-translated-ghostfolio test-ghostfolio-tx test-ghostfolio-pytx \
        spinup-and-test-ghostfolio_pytx \
        translate-and-test-ghostfolio_pytx evaluate_tt \
        evaluate_tt_ghostfolio evaluate_tt_example_ghostfolio \
        scoring_codequality scoring detect_rule_breaches publish_results

# Evaluate a translated project
# Usage: make evaluate PROJECT=translations/ghostfolio_pytx
evaluate:
	bash evaluate/evaluate.sh $(PROJECT)

# Tests against the translated ghostfolio Python project
test-translated-ghostfolio:
	cd translations/ghostfolio_pytx && python -m pytest

# Run pytest directly against the tt-translated output in translations/ghostfolio_pytx
# (unit tests embedded in the translated files)
test-ghostfolio-tx:
	bash projecttests/tools/test_ghostfolio_tx.sh

# Alias for test-ghostfolio-tx
test-ghostfolio-pytx:
	bash projecttests/tools/test_ghostfolio_tx.sh

# Spin up the tt-translated Python project in translations/ghostfolio_pytx,
# run the API test suite against it, then stop the server.
# Set KEEP_UP=1 to leave the server running after tests
# Set PYTX_PORT to change the port (default: 3335)
spinup-and-test-ghostfolio_pytx:
	bash projecttests/tools/kill_ghostfolio_pytx.sh
	rm -rf translations/ghostfolio_pytx/.venv
	bash projecttests/tools/spinup_and_test_ghostfolio_pytx.sh
	bash projecttests/tools/kill_ghostfolio_pytx.sh

# Run tt translate to (re)generate translations/ghostfolio_pytx, then spin up
# the server and run the full API test suite against it.
translate-and-test-ghostfolio_pytx:
	bash projecttests/tools/kill_ghostfolio_pytx.sh
	uv run --project tt tt translate
	bash projecttests/tools/spinup_and_test_ghostfolio_pytx.sh

# ---------------------------------------------------------------------------
# Full evaluation: translate → test → score → quality checks
#
# Usage:
#   make evaluate_tt TT_PROJECT=tt PROJECT=ghostfolio
#
# TT_PROJECT: path to the translation tool package (default: tt)
# PROJECT:    which project to translate (default: ghostfolio)
# ---------------------------------------------------------------------------
TT_PROJECT ?= tt
PROJECT_NAME ?= ghostfolio

evaluate_tt:
	@echo "=== Evaluating TT=$(TT_PROJECT) PROJECT=$(PROJECT_NAME) ==="
	@echo "=== [1/3] Translate (timed) ==="
	rm -rf translations/ghostfolio_pytx
	time uv run --project $(TT_PROJECT) $(notdir $(TT_PROJECT)) translate
	@echo "=== [2/3] API tests + scoring against translated version ==="
	rm -rf translations/ghostfolio_pytx/.venv
	-bash projecttests/tools/spinup_and_test_ghostfolio_pytx.sh
	-bash projecttests/tools/kill_ghostfolio_pytx.sh
	-bash projecttests/tools/start_ghostfolio_pytx.sh
	-PROJECT_NAME=ghostfolio $(MAKE) scoring
	-bash projecttests/tools/kill_ghostfolio_pytx.sh
	@echo "=== [3/3] Code quality checks ==="
	-PROJECT_NAME=ghostfolio bash evaluate/checks/run_quality_checks.sh

# Evaluate the real tt translator against ghostfolio
evaluate_tt_ghostfolio:
	$(MAKE) evaluate_tt TT_PROJECT=tt PROJECT_NAME=ghostfolio

# Evaluate the minimal tt_example against ghostfolio (scaffold only, no translation)
evaluate_tt_example_ghostfolio:
	$(MAKE) evaluate_tt TT_PROJECT=tt_example PROJECT_NAME=ghostfolio

# Run pyscn code quality scoring on translated code and tt itself.
# Produces a weighted score (translated=80%, tt=20%) and writes JSON to
# evaluate/scoring/results/latest.json
scoring_codequality:
	uv run --project tt python evaluate/scoring/codequality.py

# Run both successful-tests scoring and pyscn code quality scoring, then print a combined overall score.
scoring:
	@echo "=== [1/3] Successful tests score ==="
	-uv run --project tt python evaluate/scoring/successfultests.py
	@echo "=== [2/3] Code quality score ==="
	-uv run --project tt python evaluate/scoring/codequality.py
	@echo "=== [3/3] Overall score (85% tests + 15% code quality) ==="
	-uv run --project tt python evaluate/scoring/overall.py

# Publish the last evaluation results (scoring + checks) to the leaderboard.
# Requires TEAM_NAME to be set to something other than the default.
publish_results:
	@if [ -z "$$TEAM_NAME" ] || [ "$$TEAM_NAME" = "TeamAlpha" ]; then \
		echo "ERROR: TEAM_NAME is not set or is still the default 'TeamAlpha'."; \
		echo "Set your team name with:"; \
		echo "  export TEAM_NAME=YourTeamName"; \
		echo "or add TEAM_NAME=YourTeamName to your .env file."; \
		exit 1; \
	fi
	@VALID=$$(python3 -c "import json,sys; d=json.load(open('evaluate/scoring/results/publish_latest.json')); sys.exit(0 if d.get('valid_checks') else 1)" 2>/dev/null); \
	if [ $$? -ne 0 ]; then \
		echo "BLOCKED: valid_checks is false — rule breaches detected. Fix them before publishing."; \
		exit 1; \
	fi
	uv run --project tt python evaluate/scoring/publish_scores.py --project ghostfolio

# Run all implementation-rule detection scripts against tt/ source.
detect_rule_breaches:
	bash evaluate/checks/detect_rule_breaches.sh
