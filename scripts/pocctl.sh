#!/bin/bash
# Playerok Cardinal — управление systemd-сервисом на Linux VPS.
# Использование: sudo pocctl [start|stop|restart|status|logs|update|health]

set -euo pipefail

POC_USER="${POC_USER:-poc}"
POC_HOME="/home/${POC_USER}"
POC_DIR="${POC_HOME}/PlayerokCardinal"
POC_VENV="${POC_HOME}/pyvenv"
POC_SERVICE="PlayerokCardinal@${POC_USER}.service"

usage() {
    cat <<EOF
Playerok Cardinal — управление сервисом

  sudo pocctl start     — запустить бота
  sudo pocctl stop      — остановить
  sudo pocctl restart   — перезапустить
  sudo pocctl status    — статус (systemctl)
  sudo pocctl logs      — последние 100 строк journalctl
  sudo pocctl update    — git pull + pip install + restart
  sudo pocctl health    — проверка версии, venv, websocket, сервиса

Переменные окружения:
  POC_USER=poc          — пользователь Linux, от имени которого работает бот

Systemd unit: ${POC_SERVICE}
EOF
}

require_root() {
    if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
        echo "Запустите с sudo: sudo pocctl $*" >&2
        exit 1
    fi
}

unit_name() {
    echo "PlayerokCardinal@${POC_USER}"
}

cmd_start() {
    require_root start
    systemctl start "$(unit_name)"
    systemctl status "$(unit_name)" -n 5 --no-pager || true
}

cmd_stop() {
    require_root stop
    systemctl stop "$(unit_name)"
}

cmd_restart() {
    require_root restart
    systemctl daemon-reload
    systemctl restart "$(unit_name)"
    sleep 2
    systemctl status "$(unit_name)" -n 10 --no-pager || true
}

cmd_status() {
    require_root status
    systemctl status "$(unit_name)" -n 50 --no-pager
}

cmd_logs() {
    require_root logs
    journalctl -u "$(unit_name)" -n 100 --no-pager
}

cmd_update() {
    require_root update
    if [[ ! -d "${POC_DIR}/.git" ]]; then
        echo "Ошибка: ${POC_DIR} не является git-репозиторием." >&2
        exit 1
    fi
    git config --global --add safe.directory "${POC_DIR}" 2>/dev/null || true
    sudo -u "${POC_USER}" git -C "${POC_DIR}" pull
    sudo -u "${POC_USER}" "${POC_VENV}/bin/pip" install -r "${POC_DIR}/requirements.txt"
    systemctl daemon-reload
    systemctl restart "$(unit_name)"
    sleep 2
    if systemctl is-active --quiet "$(unit_name)"; then
        echo "Обновление завершено, сервис активен."
    else
        echo "Ошибка: сервис не запустился после обновления." >&2
        journalctl -u "$(unit_name)" -n 30 --no-pager
        exit 1
    fi
}

cmd_health() {
    echo "=== Playerok Cardinal health ==="
    echo "User:    ${POC_USER}"
    echo "Service: $(unit_name)"
    echo "Dir:     ${POC_DIR}"
    echo "Venv:    ${POC_VENV}"

    if [[ -f "${POC_DIR}/main.py" ]]; then
        version=$(grep -m1 '^VERSION' "${POC_DIR}/main.py" | sed 's/.*"\(.*\)".*/\1/' || echo "?")
        echo "Version: ${version}"
    else
        echo "Version: main.py not found"
    fi

    if [[ -f "${POC_DIR}/configs/_main.cfg" ]]; then
        echo "Config:  OK (_main.cfg exists)"
    else
        echo "Config:  MISSING (_main.cfg)"
    fi

    if [[ -x "${POC_VENV}/bin/python" ]]; then
        if sudo -u "${POC_USER}" "${POC_VENV}/bin/python" -c "import websocket" 2>/dev/null; then
            ws_ver=$(sudo -u "${POC_USER}" "${POC_VENV}/bin/python" -c "import websocket; print(websocket.__version__)" 2>/dev/null || echo "?")
            echo "Websocket: OK (${ws_ver})"
        else
            echo "Websocket: FAIL (pip install websocket-client in ${POC_VENV})"
        fi
    else
        echo "Venv python: MISSING"
    fi

    if systemctl is-active --quiet "$(unit_name)" 2>/dev/null; then
        echo "Service: active (running)"
    elif systemctl is-enabled --quiet "$(unit_name)" 2>/dev/null; then
        echo "Service: enabled but not running ($(systemctl is-active "$(unit_name)" 2>/dev/null || echo inactive))"
    else
        echo "Service: not found or disabled"
        echo "  Правильная команда: sudo systemctl restart $(unit_name)"
    fi
}

main() {
    local cmd="${1:-}"
    case "${cmd}" in
        start)   cmd_start ;;
        stop)    cmd_stop ;;
        restart) cmd_restart ;;
        status)  cmd_status ;;
        logs)    cmd_logs ;;
        update)  cmd_update ;;
        health)  cmd_health ;;
        -h|--help|help|"")
            usage
            [[ -z "${cmd}" ]] && exit 0
            ;;
        *)
            echo "Неизвестная команда: ${cmd}" >&2
            usage
            exit 1
            ;;
    esac
}

main "$@"
