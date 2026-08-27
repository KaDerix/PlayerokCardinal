#!/bin/bash
# Playerok Cardinal — Linux installer
set -euo pipefail
commands='17'

R=$'\033[0m'
B=$'\033[1m'
RED=$'\033[1;91m'
YEL=$'\033[1;93m'
GRN=$'\033[1;92m'

# палитра как в Utils/banner.py
B1=$'\033[38;5;27m'
B2=$'\033[38;5;33m'
B3=$'\033[38;5;39m'
B4=$'\033[38;5;45m'
B5=$'\033[38;5;51m'
W=$'\033[38;5;255m'
D=$'\033[38;5;245m'
F=$'\033[38;5;238m'

W_INNER=50
BOX_W=50

_repeat() {
  local c="$1" n="$2" i out=
  for ((i = 0; i < n; i++)); do out+="$c"; done
  printf '%s' "$out"
}

_row() {
  local visible="$1"
  local display="${2:-$1}"
  local pad=$((W_INNER - ${#visible}))
  ((pad < 0)) && pad=0
  local left=$((pad / 2))
  local right=$((pad - left))
  printf "${B1}║${R}%*s%s%*s${B1}║${R}\n" "$left" "" "$display" "$right" ""
}

print_banner() {
  local ver="${1:-}"
  echo ""
  printf "${B1}╔%s╗${R}\n" "$(_repeat '═' "$W_INNER")"
  _row ""
  _row "PLAYEROK  CARDINAL" "${W}${B}PLAYEROK${R}  ${B5}${B}CARDINAL${R}"
  _row "автоматизация  playerok.com" "${D}автоматизация${R}  ${B3}${B}playerok.com${R}"
  _row "* . . . . . . . . . . . . . . *" "${B2}*${R} ${F}. . . . . . . . . . . . . .${R} ${B2}*${R}"
  printf "${B2}╠%s╣${R}\n" "$(_repeat '─' "$W_INNER")"
  _row ""
  if [[ -n "$ver" ]]; then
    _row "v${ver}" "${B4}${B}v${ver}${R}"
  else
    _row "Linux installer" "${B4}${B}Linux installer${R}"
  fi
  _row "github.com/KaDerix/PlayerokCardinal" "${D}github.com/KaDerix/PlayerokCardinal${R}"
  _row "t.me/KaDerix" "${B4}t.me/KaDerix${R}"
  _row ""
  printf "${B1}╚%s╝${R}\n" "$(_repeat '═' "$W_INNER")"
  echo ""
}

# строка рамки: видимая ширина ровно BOX_W (цвета не считаются)
_box_row() {
  local visible="$1"
  local display="${2:-$1}"
  if ((${#visible} > BOX_W)); then
    visible="${visible:0:$((BOX_W - 1))}…"
    display="$visible"
  fi
  printf "  ${B1}│${R}%s%*s${B1}│${R}\n" "$display" "$((BOX_W - ${#visible}))" ""
}

box() {
  local title="$1"
  echo ""
  printf "  ${B1}┌%s┐${R}\n" "$(_repeat '─' "$BOX_W")"
  _box_row "$title" "${B4}${B}${title}${R}"
  printf "  ${B1}└%s┘${R}\n" "$(_repeat '─' "$BOX_W")"
  echo ""
}

print_finish() {
  local user="$1"
  local svc="PlayerokCardinal@${user}"
  local cmd

  echo -e "  ${GRN}${B}Установка завершена${R}"
  echo ""
  echo -e "  ${YEL}${B}Сделай скриншот${R} ${D}— пригодится для поддержки${R}"
  echo ""
  printf "  ${D}%-10s${R} ${B}%s${R}\n" "Сервис" "$svc"
  printf "  ${D}%-10s${R} ${GRN}%s${R}\n" "Статус" "active"
  printf "  ${D}%-10s${R} %s\n" "Telegram" "напиши своему боту"
  echo ""

  printf "  ${B1}┌%s┐${R}\n" "$(_repeat '─' "$BOX_W")"
  _box_row " Управление" " ${B}Управление${R}"
  printf "  ${B1}├%s┤${R}\n" "$(_repeat '─' "$BOX_W")"
  for cmd in \
    " sudo pocctl restart" \
    " sudo pocctl logs" \
    " sudo pocctl health" \
    " systemctl status ${svc}"
  do
    _box_row "$cmd" "$cmd"
  done
  printf "  ${B1}└%s┘${R}\n" "$(_repeat '─' "$BOX_W")"
  echo ""
  echo -e "  ${D}Подсказка:${R} /home/${user}/POC_SERVICE.txt"
  echo -e "  ${RED}*${R} ${D}Не пиши PlayerokCardinalPOC — после @ имя пользователя (${user})${R}"
  echo ""
}

fail() {
  local msg="$1"
  local step="$2"
  echo ""
  echo -e "${RED}${B}✗ Ошибка${R} ${D}(${step}/${commands})${R}"
  echo -e "${RED}${msg}${R}"
  echo ""
  exit 2
}

ok() {
  echo -e "  ${GRN}✓${R} $1"
}

info() {
  echo -e "  ${B3}›${R} $1"
}

ask() {
  echo -ne "  ${B4}${B}?${R} $1 "
}

_clear() { clear 2>/dev/null || printf '\033c' || true; }

# ── старт ──────────────────────────────────────────────
_clear
print_banner

echo -e "  ${D}GitHub${R}    ${B3}github.com/KaDerix/PlayerokCardinal${R}"
echo -e "  ${D}Telegram${R}  ${B4}t.me/KaDerix${R}"
echo ""
echo -e "  ${D}Установщик создаст пользователя Linux и systemd-сервис.${R}"
echo ""

ask "Имя пользователя для бота ${D}(poc / cardinal)${R}:"
while true; do
  read username
  username="${username,,}"  # Linux: всегда lowercase (POC → poc)
  if [[ "$username" =~ ^[a-z][a-z0-9_-]+$ ]]; then
    if id "$username" &>/dev/null; then
      echo ""
      info "аккаунт ${B}${username}${R} ещё в системе ${D}(/etc/passwd)${R}"
      info "удаление папки по SFTP пользователя ${B}не${R} удаляет"
      echo ""
      ask "y = использовать  /  r = удалить и создать заново  /  n = другое имя:"
      read use_existing
      case "$use_existing" in
        [yY]|[yY][eE][sS])
          ok "используем существующего: ${B}${username}${R}"
          break
          ;;
        [rR]|[rR][eE][cC][rR][eE][aA][tT][eE])
          info "останавливаю сервис (если был)…"
          sudo systemctl stop "PlayerokCardinal@${username}" 2>/dev/null || true
          sudo systemctl disable "PlayerokCardinal@${username}" 2>/dev/null || true
          # -r удаляет и home; если home уже снесли — fallback без -r
          if sudo userdel -r "$username" 2>/dev/null || sudo userdel "$username" 2>/dev/null; then
            ok "пользователь ${B}${username}${R} удалён — создадим заново"
            break
          else
            echo -e "  ${RED}Не удалось удалить ${username}.${R}"
            echo -e "  ${D}Вручную: sudo userdel -r ${username}${R}"
            ask "Другое имя:"
          fi
          ;;
        *)
          ask "Другое имя:"
          ;;
      esac
    else
      break
    fi
  else
    echo -e "  ${RED}Недопустимое имя.${R} ${D}латиница, цифра, _/- ; начинать с буквы${R}"
    ask "Повтори:"
  fi
done

echo ""
ok "сервис: ${B}PlayerokCardinal@${username}${R}"
info "после @ — имя пользователя Linux"
echo ""
sleep 1

distro_version=$(lsb_release -rs 2>/dev/null || echo "unknown")

# ── репозитории ────────────────────────────────────────
_clear
print_banner
box "1/6  Репозитории и пакеты"

if ! sudo apt update ; then
  fail "apt update" "1"
fi
ok "apt update"

if ! sudo apt install -y software-properties-common ; then
  fail "software-properties-common" "2"
fi
ok "software-properties-common"

case $distro_version in
  "22.04" | "22.10" | "23.04" | "23.10" | "24.04" | "24.10" | "12")
    ;;
  "11")
    if ! sudo apt install -y gnupg ; then
      fail "gnupg" "3.1"
    fi
    if ! sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys BA6932366A755776 ; then
      fail "apt-key" "3.2"
    fi
    if ! sudo add-apt-repository -s "deb https://ppa.launchpadcontent.net/deadsnakes/ppa/ubuntu focal main" ; then
      fail "deadsnakes repo" "3.3"
    fi
    if ! sudo tee /etc/apt/preferences.d/10deadsnakes-ppa >/dev/null <<EOF
Package: *
Pin: release o=LP-PPA-deadsnakes
Pin-Priority: 100
EOF
    then
      fail "pin preferences" "3.4"
    fi
    ;;
  *)
    if ! sudo add-apt-repository -y ppa:deadsnakes/ppa ; then
      fail "deadsnakes ppa" "3"
    fi
    ;;
esac

if ! sudo apt update ; then
  fail "apt update (2)" "4"
fi
ok "репозитории готовы"

if ! sudo apt install -y curl ; then
  fail "curl" "5"
fi
ok "curl"

if ! sudo apt install -y unzip ; then
  fail "unzip" "6"
fi
ok "unzip"

# ── Python ──────────────────────────────────────────────
_clear
print_banner
box "2/6  Python"

case $distro_version in
  "24.04" | "24.10")
    if ! sudo apt install -y python3.12 python3.12-dev python3.12-gdbm python3.12-venv ; then
      fail "python3.12" "7"
    fi
    ok "python3.12"
    ;;
  *)
    if ! sudo apt install -y python3.11 python3.11-dev python3.11-gdbm python3.11-venv ; then
      fail "python3.11" "7"
    fi
    ok "python3.11"
    ;;
esac

# ── пользователь + venv ─────────────────────────────────
_clear
print_banner
box "3/6  Пользователь и venv"

ensure_home() {
  local u="$1"
  local home="/home/$u"
  if [[ -d "$home" ]]; then
    return 0
  fi
  info "нет ${B}${home}${R} — восстанавливаю home"
  if command -v mkhomedir_helper >/dev/null 2>&1; then
    sudo mkhomedir_helper "$u" 2>/dev/null || true
  fi
  if [[ ! -d "$home" ]]; then
    if ! sudo mkdir -p "$home"; then
      fail "mkdir home" "8.1"
    fi
    sudo cp -a /etc/skel/. "$home/" 2>/dev/null || true
  fi
  if ! sudo chown -R "$u:$u" "$home"; then
    fail "chown home" "8.2"
  fi
  sudo chmod 755 "$home" || true
  ok "home: ${B}${home}${R}"
}

if id "$username" &>/dev/null; then
  info "пользователь ${B}${username}${R} уже существует"
  ensure_home "$username"
else
  if ! sudo useradd -m "$username" ; then
    fail "useradd" "8"
  fi
  ok "создан пользователь ${B}${username}${R}"
fi

venv_exists=0
if [[ -x "/home/$username/pyvenv/bin/python" ]]; then
  venv_exists=1
  info "venv уже есть — обновляю pip"
fi

if [[ "$venv_exists" -eq 0 ]]; then
  case $distro_version in
    "24.04" | "24.10")
      if ! sudo -u "$username" python3.12 -m venv "/home/$username/pyvenv" ; then
        fail "venv python3.12" "9"
      fi
      ;;
    *)
      if ! sudo -u "$username" python3.11 -m venv "/home/$username/pyvenv" ; then
        fail "venv python3.11" "9"
      fi
      ;;
  esac
  ok "venv создан"
fi

if ! sudo "/home/$username/pyvenv/bin/python" -m ensurepip --upgrade ; then
  fail "ensurepip" "10"
fi
if ! sudo -u "$username" "/home/$username/pyvenv/bin/python" -m pip install --upgrade pip ; then
  fail "pip upgrade" "11"
fi
if ! sudo chown -hR "$username:$username" "/home/$username/pyvenv" ; then
  fail "chown venv" "12"
fi
ok "pip готов"

# ── клон / обновление ───────────────────────────────────
_clear
print_banner
box "4/6  PlayerokCardinal"

if ! sudo apt install -y git ; then
  fail "git" "13"
fi
ok "git"

gh_repo="KaDerix/PlayerokCardinal"
poc_dir="/home/$username/PlayerokCardinal"

sudo git config --global --add safe.directory "$poc_dir" 2>/dev/null || true

if [[ -d "$poc_dir/.git" ]]; then
  info "репозиторий найден — git pull"
  if ! sudo -u "$username" git -C "$poc_dir" pull ; then
    fail "git pull" "14"
  fi
  ok "обновлено"
elif [[ -d "$poc_dir" ]]; then
  echo -e "  ${RED}Папка $poc_dir есть, но это не git-репозиторий.${R}"
  echo -e "  ${D}Переименуй/удали её и запусти установку снова.${R}"
  exit 2
else
  if ! sudo -u "$username" git clone "https://github.com/${gh_repo}.git" "$poc_dir" ; then
    fail "git clone" "14"
  fi
  ok "клонировано"
fi

if ! sudo -u "$username" "/home/$username/pyvenv/bin/pip" install -U -r "$poc_dir/requirements.txt" ; then
  fail "pip install -r requirements.txt" "15"
fi
ok "зависимости установлены"

# ── systemd + pocctl ────────────────────────────────────
_clear
print_banner
box "5/6  Systemd и pocctl"

if ! sudo ln -sf "/home/$username/PlayerokCardinal/PlayerokCardinal@.service" /etc/systemd/system/PlayerokCardinal@.service ; then
  fail "symlink service" "16"
fi
ok "systemd unit"

if ! sudo install -m 755 "/home/$username/PlayerokCardinal/scripts/pocctl.sh" /usr/local/bin/pocctl ; then
  fail "pocctl" "16.1"
fi
ok "pocctl"

sudo tee /etc/default/pocctl >/dev/null <<EOF
POC_USER=${username}
EOF
chmod 644 /etc/default/pocctl

sudo tee "/home/$username/POC_SERVICE.txt" >/dev/null <<EOF
Playerok Cardinal — управление сервисом
======================================
Пользователь Linux: ${username}
Systemd unit: PlayerokCardinal@${username}

sudo systemctl restart PlayerokCardinal@${username}
sudo systemctl stop PlayerokCardinal@${username}
sudo systemctl start PlayerokCardinal@${username}
sudo systemctl status PlayerokCardinal@${username} -n100
sudo systemctl enable PlayerokCardinal@${username}

Сокращения:
  sudo pocctl restart
  sudo pocctl logs
  sudo pocctl health

НЕ используй: PlayerokCardinalPOC
EOF
sudo chown "$username:$username" "/home/$username/POC_SERVICE.txt"
ok "подсказка → /home/${username}/POC_SERVICE.txt"

# ── локаль ──────────────────────────────────────────────
_clear
print_banner
box "6/6  Локаль и настройка"

case $distro_version in
  "11" | "12")
    if ! sudo apt install -y locales locales-all ; then
      fail "locales" "17"
    fi
    ;;
  *)
    if ! sudo apt install -y language-pack-en ; then
      fail "language-pack-en" "17"
    fi
    ;;
esac
ok "локаль"

# ── first setup ─────────────────────────────────────────
_clear
print_banner
box "Первичная настройка"

info "ответь на вопросы на экране"
echo ""
sleep 2

if [ ! -f "/home/$username/PlayerokCardinal/configs/_main.cfg" ]; then
  sudo -u "$username" LANG=en_US.utf8 "/home/$username/pyvenv/bin/python" "/home/$username/PlayerokCardinal/main.py" <&1

  if [ ! -f "/home/$username/PlayerokCardinal/configs/_main.cfg" ]; then
    echo -e "\n  ${RED}Конфиг не создан.${R}"
    echo -e "  ${D}Запусти вручную:${R}"
    echo -e "  ${B3}sudo -u $username bash -c 'cd /home/$username/PlayerokCardinal && /home/$username/pyvenv/bin/python main.py'${R}"
    exit 1
  fi
  echo ""
  ok "первичная настройка завершена"
else
  info "конфиг уже есть — setup пропущен"
  echo ""
  ask "Добавить Telegram proxy? ${D}(y/n)${R}:"
  read edit_config
  case "$edit_config" in
    [yY]|[yY][eE][sS])
      sudo -u "$username" LANG=en_US.utf8 "/home/$username/pyvenv/bin/python" -W ignore::SyntaxWarning "/home/$username/PlayerokCardinal/setup_telegram_proxy.py" <&1
      ;;
    *)
      info "пропущено"
      ;;
  esac
fi

sleep 1

sudo systemctl daemon-reload
sudo systemctl enable "PlayerokCardinal@$username.service"
sudo systemctl restart "PlayerokCardinal@$username.service"
sleep 3

if ! systemctl is-active --quiet "PlayerokCardinal@$username.service" ; then
  echo ""
  echo -e "  ${RED}${B}Сервис не запустился:${R} PlayerokCardinal@${username}"
  echo -e "  ${D}Последние строки лога:${R}"
  journalctl -u "PlayerokCardinal@$username.service" -n 40 --no-pager
  echo -e "\n  ${D}Проверка:${R} ${B3}sudo pocctl health${R}"
  exit 1
fi

# ── финал ───────────────────────────────────────────────
_clear
print_banner
print_finish "$username"

ask "Скриншот сделан? Enter → выход"
read
_clear
