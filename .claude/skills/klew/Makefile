# klew — drive the Playwright CLI and the selector pipeline.
#
# Quick start (against a local app):
#   make -C .claude/skills/klew install
#   make -C .claude/skills/klew config URL=http://127.0.0.1:8123/ TESTID_ATTR=data-test
#   make -C .claude/skills/klew open URL=http://127.0.0.1:8123/
#   # ...explore with `playwright-cli` in WORKDIR, collect candidates.json...
#   make -C .claude/skills/klew cache APP=todomvc CANDIDATES=candidates.json APPROVED=1
#   make -C .claude/skills/klew pom   APP=todomvc
#   make -C .claude/skills/klew handoff APP=todomvc POM_DEST=../../../page-objects
#
# In a sandboxed/CI image, point at a pre-installed Chromium and drop the sandbox:
#   make config URL=... PW_EXECUTABLE=/opt/pw-browsers/chromium-*/chrome-linux/chrome PW_SANDBOX=false

SKILL_DIR := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
SCRIPTS   := $(SKILL_DIR)/scripts
PY        ?= python3
CLI       ?= playwright-cli

# APP        application slug         URL        app base URL
# WORKDIR    cli.config.json + snapshots live here
# CANDIDATES resolved-selector batch to cache (for `make cache`)
# POM_DEST   optional dir to copy the exported POM into (for `make handoff`)
# MIN_CONF   export_pom --min-confidence threshold
APP        ?= demo
URL        ?=
WORKDIR    ?= $(SKILL_DIR)/.work
CANDIDATES ?= candidates.json
POM_DEST   ?=
MIN_CONF   ?= 0.0

# Authoring (record → journey / NL → journey): CODEGEN or PLAN, NAME slug, REQ tag
REPO       := $(abspath $(SKILL_DIR)/../../..)
CODEGEN    ?=
PLAN       ?=
NAME       ?=
REQ        ?=
OUTDIR     ?= $(REPO)/e2e

# Browser knobs (handy in headless/CI containers):
# PW_EXECUTABLE  path to a pre-installed chromium (optional)
# PW_SANDBOX     set false when running as root
TESTID_ATTR   ?= data-testid
PW_EXECUTABLE ?=
PW_SANDBOX    ?= true

.PHONY: help install config plan record author author-nl open snapshot cache cache-delta cache-check knowledge-check audit-plan audit-apply pom handoff clean

help:            ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-13s\033[0m %s\n", $$1, $$2}'

install:         ## Install the Playwright CLI globally (+ its agent skills)
	npm install -g @playwright/cli@latest
	$(CLI) install --skills || true

config:          ## Write $(WORKDIR)/.playwright/cli.config.json from the vars above
	@mkdir -p "$(WORKDIR)/.playwright"
	@{ \
	  printf '{\n  "testIdAttribute": "%s",\n' "$(TESTID_ATTR)"; \
	  printf '  "browser": { "browserName": "chromium", "launchOptions": { "headless": true'; \
	  [ "$(PW_SANDBOX)" = "false" ] && printf ', "chromiumSandbox": false'; \
	  [ -n "$(PW_EXECUTABLE)" ] && printf ', "executablePath": "%s"' "$(PW_EXECUTABLE)"; \
	  printf ' } }\n}\n'; \
	} > "$(WORKDIR)/.playwright/cli.config.json"
	@echo "wrote $(WORKDIR)/.playwright/cli.config.json"

plan:            ## Cache-first: what does a goal need to explore? (NEEDS=name,name...)
	@test -n "$(NEEDS)" || { echo "set NEEDS=<comma-separated logical names>"; exit 2; }
	$(PY) $(SCRIPTS)/plan_goal.py --app "$(APP)" --needs "$(NEEDS)" $(if $(GOAL),--goal "$(GOAL)")

record:          ## No-code: record a flow (headed, LOCAL) → CODEGEN file (needs URL + CODEGEN)
	@test -n "$(URL)" || { echo "set URL=<app url>"; exit 2; }
	@test -n "$(CODEGEN)" || { echo "set CODEGEN=<out.spec.ts>"; exit 2; }
	cd "$(REPO)/e2e" && npx playwright codegen "$(URL)" -o "$(CODEGEN)"

author:          ## Normalize a recording → klew journey + candidate selectors (CODEGEN, NAME)
	@test -n "$(CODEGEN)" || { echo "set CODEGEN=<recording.spec.ts>"; exit 2; }
	@test -n "$(NAME)" || { echo "set NAME=<journey slug>"; exit 2; }
	$(PY) $(SCRIPTS)/author_journey.py --app "$(APP)" --codegen "$(CODEGEN)" \
	  --name "$(NAME)" $(if $(REQ),--req "$(REQ)") --out-dir "$(OUTDIR)"

author-nl:       ## Render a natural-language journey PLAN → klew journey (PLAN, NAME opt.)
	@test -n "$(PLAN)" || { echo "set PLAN=<plan.json>"; exit 2; }
	$(PY) $(SCRIPTS)/author_nl.py --app "$(APP)" --plan "$(PLAN)" \
	  $(if $(NAME),--name "$(NAME)") $(if $(REQ),--req "$(REQ)") --out-dir "$(OUTDIR)"

open:            ## Open URL in the CLI browser (from WORKDIR so it reads the config)
	@test -n "$(URL)" || { echo "set URL=<app url>"; exit 2; }
	cd "$(WORKDIR)" && $(CLI) open "$(URL)"

snapshot:        ## Capture an accessibility snapshot of the active tab
	cd "$(WORKDIR)" && $(CLI) snapshot

cache:           ## Persist a resolved batch (guarded: pass APPROVED=1 for human sign-off)
	@test "$(APPROVED)" = "1" || { echo "REFUSING: pass APPROVED=1 to confirm you reviewed the batch"; exit 2; }
	$(PY) $(SCRIPTS)/cache_selectors.py --app "$(APP)" $(if $(URL),--base-url "$(URL)") \
	  --approved --input "$(CANDIDATES)"

cache-delta:     ## Write only NEW/CHANGED selectors (for a PR diff; still needs APPROVED=1)
	@test "$(APPROVED)" = "1" || { echo "REFUSING: pass APPROVED=1 (=propose via PR)"; exit 2; }
	$(PY) $(SCRIPTS)/cache_selectors.py --app "$(APP)" $(if $(URL),--base-url "$(URL)") \
	  --approved --changed-only --input "$(CANDIDATES)"

cache-check:     ## Does the JSON need updating? Dry-run a delta (no write, no APPROVED)
	$(PY) $(SCRIPTS)/cache_selectors.py --app "$(APP)" --dry-run --changed-only --input "$(CANDIDATES)"

knowledge-check: ## Is the app's knowledge note stale vs the cache? (deterministic, no write)
	$(PY) $(SCRIPTS)/knowledge_check.py --app "$(APP)" $(if $(JSON),--json)

audit-plan:      ## Print the live re-validation checklist for a cached app
	$(PY) $(SCRIPTS)/audit_selectors.py --app "$(APP)" --plan

audit-apply:     ## Apply audit results (RESULTS=results.json of {name: match_count})
	@test -n "$(RESULTS)" || { echo "set RESULTS=<results.json>"; exit 2; }
	$(PY) $(SCRIPTS)/audit_selectors.py --app "$(APP)" --apply-results "$(RESULTS)"

pom:             ## Export the approved cache to a Playwright Page Object
	$(PY) $(SCRIPTS)/export_pom.py --app "$(APP)" --min-confidence "$(MIN_CONF)"

handoff:         ## pom + copy the POM into POM_DEST for a test project (e.g. yilsf specs)
handoff: pom
	@test -n "$(POM_DEST)" || { echo "set POM_DEST=<dir>"; exit 2; }
	@mkdir -p "$(POM_DEST)"
	cp "$(SKILL_DIR)/knowledge/$(APP)/$(APP).pom.ts" "$(POM_DEST)/"
	@echo "copied $(APP).pom.ts -> $(POM_DEST)/"

clean:           ## Close all browser sessions and remove the work dir
	-$(CLI) close-all
	rm -rf "$(WORKDIR)"
