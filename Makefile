# 2Walks — Makefile (удобные обёртки для деплоя на домашний прод-сервер).
#
# Деплой = обновление web 24/7 на Ubuntu-сервере (см. CLAUDE.md «Production: web 24/7»).
# SSH интерактивный (ключ/пароль) — запускать вручную: `make deploy`.
#
# Переопределение хоста (mDNS вместо IP):
#   make deploy HOST=aleksey@aleksey-H61M-DS2H.local

HOST       ?= aleksey@192.168.0.155
REMOTE_DIR ?= ~/2Walks
SERVICE    ?= 2walks

.PHONY: deploy status logs help

## deploy: git pull + pip install + restart сервиса на сервере
deploy:
	ssh $(HOST) "cd $(REMOTE_DIR) && git pull && .venv/bin/pip install -r requirements.txt && sudo systemctl restart $(SERVICE) && echo '--- STATUS ---' && systemctl is-active $(SERVICE)"

## status: показать состояние systemd-юнита на сервере
status:
	ssh $(HOST) "systemctl status $(SERVICE) --no-pager"

## logs: последние 50 строк журнала сервиса (follow: make logs FOLLOW=-f)
logs:
	ssh $(HOST) "journalctl -u $(SERVICE) -n 50 --no-pager $(FOLLOW)"

## help: список доступных целей
help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## //'
