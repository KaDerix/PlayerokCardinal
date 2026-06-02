#!/bin/bash
commands='17'

RED='\033[1;91m'
CYAN='\033[1;96m'
GREEN='\033[1;92m'
PURPLE_LIGHT='\033[5;35m'
RESET='\033[0m'

start_process_line="${PURPLE_LIGHT}################################################################################"
end_process_line="################################################################################${RESET}"

logo="\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m
\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;52m>\e[0m\e[38;5;88m|\e[0m\e[38;5;124m}\e[0m\e[38;5;124m]\e[0m\e[38;5;124m]\e[0m\e[38;5;88m?\e[0m\e[38;5;88m?\e[0m\e[38;5;124m+\e[0m\e[38;5;124m+\e[0m\e[38;5;124m+\e[0m\e[38;5;124m+\e[0m\e[38;5;88m?\e[0m\e[38;5;88m?\e[0m\e[38;5;124m]\e[0m\e[38;5;124m]\e[0m\e[38;5;124m]\e[0m\e[38;5;88m|\e[0m\e[38;5;52m>\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m
\e[38;5;0m.\e[0m\e[38;5;0m'\e[0m\e[38;5;15mP\e[0m\e[38;5;15mL\e[0m\e[38;5;15mA\e[0m\e[38;5;15mY\e[0m\e[38;5;15mE\e[0m\e[38;5;15mR\e[0m\e[38;5;15mO\e[0m\e[38;5;15mK\e[0m\e[38;5;0m \e[0m\e[38;5;15mC\e[0m\e[38;5;15mA\e[0m\e[38;5;15mR\e[0m\e[38;5;15mD\e[0m\e[38;5;15mI\e[0m\e[38;5;15mN\e[0m\e[38;5;15mA\e[0m\e[38;5;15mL\e[0m\e[38;5;0m'\e[0m\e[38;5;0m.\e[0m
\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;52m>\e[0m\e[38;5;88m|\e[0m\e[38;5;124m]\e[0m\e[38;5;124m]\e[0m\e[38;5;124m+\e[0m\e[38;5;88m?\e[0m\e[38;5;88m?\e[0m\e[38;5;124m+\e[0m\e[38;5;124m+\e[0m\e[38;5;124m+\e[0m\e[38;5;124m+\e[0m\e[38;5;88m?\e[0m\e[38;5;88m?\e[0m\e[38;5;124m+\e[0m\e[38;5;124m]\e[0m\e[38;5;124m]\e[0m\e[38;5;88m|\e[0m\e[38;5;52m>\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m
\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m\e[38;5;0m.\e[0m"

clear
echo -e $logo

echo -e "\n\n${RED} * GitHub ${CYAN}github.com/KITUSTTT/PlayerokCardinal${RESET}"
echo -e "${RED} * Telegram ${CYAN}t.me/KaDerix${RESET}"
echo -e "\n\n\n"

echo -ne "${CYAN}Режим установки:${RESET}
  ${GREEN}1${RESET} — новая установка (создать нового пользователя)
  ${GREEN}2${RESET} — переустановка / обновление (существующий пользователь, например poc)
${CYAN}Выберите [1/2]: ${RESET}"
read install_mode
install_mode="${install_mode:-1}"
reinstall=0
if [[ "$install_mode" == "2" ]]; then
  reinstall=1
fi

if [[ "$reinstall" -eq 1 ]]; then
  echo -ne "${CYAN}Введите имя существующего пользователя (например, 'poc'): ${RESET}"
  while true; do
    read username
    if [[ "$username" =~ ^[a-zA-Z][a-zA-Z0-9_-]+$ ]]; then
      if id "$username" &>/dev/null; then
        break
      else
        echo -ne "${RED}Пользователь '$username' не найден. ${CYAN}Введите существующее имя: ${RESET}"
      fi
    else
      echo -ne "${RED}Недопустимые символы. ${CYAN}Имя должно начинаться с буквы: ${RESET}"
    fi
  done
else
  echo -ne "${CYAN}Введите имя пользователя, от имени которого будет запускаться бот (например, 'poc' или 'cardinal'): ${RESET}"
  while true; do
    read username
    if [[ "$username" =~ ^[a-zA-Z][a-zA-Z0-9_-]+$ ]]; then
      if id "$username" &>/dev/null; then
        echo -ne "\n${RED}Такой пользователь уже существует. ${CYAN}Выберите режим 2 (переустановка) или введите другое имя: ${RESET}"
      else
        break
      fi
    else
      echo -ne "\n${RED}Имя пользователя содержит недопустимые символы. ${CYAN}Имя должно начинаться с буквы и может включать только буквы, цифры, '_', или '-'. Пожалуйста, введите другое имя пользователя: ${RESET}"
    fi
  done
fi

distro_version=$(lsb_release -rs)

clear
echo -e "${start_process_line}\nДобавляю репозитории...\n${end_process_line}"

if ! sudo apt update ; then
  echo -e "${start_process_line}\nПроизошла ошибка при обновлении списка пакетов. (1/${commands})\n${end_process_line}"
  exit 2
fi

if ! sudo apt install -y software-properties-common ; then
  echo -e "${start_process_line}\nПроизошла ошибка при установке software-properties-common. (2/${commands})\n${end_process_line}"
  exit 2
fi

case $distro_version in
  "22.04" | "22.10" | "23.04" | "23.10" | "24.04" | "24.10")
    ;;
  "12")
    ;;
  "11")
    if ! sudo apt install -y gnupg ; then
      echo -e "${start_process_line}\nПроизошла ошибка при установке gnupg. (3.1/${commands})\n${end_process_line}"
      exit 2
    fi

    if ! sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys BA6932366A755776 ; then
      echo -e "${start_process_line}\nПроизошла ошибка при добавлении ключа репозитория. (3.2/${commands})\n${end_process_line}"
      exit 2
    fi

    if ! sudo add-apt-repository -s "deb https://ppa.launchpadcontent.net/deadsnakes/ppa/ubuntu focal main" ; then
      echo -e "${start_process_line}\nПроизошла ошибка при добавлении репозитория. (3.3/${commands})\n${end_process_line}"
      exit 2
    fi

    if ! sudo tee /etc/apt/preferences.d/10deadsnakes-ppa >/dev/null <<EOF
Package: *
Pin: release o=LP-PPA-deadsnakes
Pin-Priority: 100
EOF
    then
      echo -e "${start_process_line}\nПроизошла ошибка при добавлении приоритета репозитория. (3.4/${commands})\n${end_process_line}"
      exit 2
    fi
    ;;
  *)
    if ! sudo add-apt-repository -y ppa:deadsnakes/ppa ; then
      echo -e "${start_process_line}\nПроизошла ошибка при добавлении репозитория. (3/${commands})\n${end_process_line}"
      exit 2
    fi
    ;;
esac

if ! sudo apt update ; then
  echo -e "${start_process_line}\nПроизошла ошибка при обновлении списка пакетов. (4/${commands})\n${end_process_line}"
  exit 2
fi

clear
echo -e "$start_process_line\nУстанавливаю необходимые пакеты...\n$end_process_line"

if ! sudo apt install -y curl ; then
  echo -e "${start_process_line}\nПроизошла ошибка при установке Curl. (5/${commands})\n${end_process_line}"
  exit 2
fi

if ! sudo apt install -y unzip ; then
  echo -e "${start_process_line}\nПроизошла ошибка при установке Unzip. (6/${commands})\n${end_process_line}"
  exit 2
fi

clear
echo -e "$start_process_line\nУстанавливаю Python...\n$end_process_line"

case $distro_version in
  "24.04" | "24.10")
    if ! sudo apt install -y python3.12 python3.12-dev python3.12-gdbm python3.12-venv ; then
      echo -e "${start_process_line}\nПроизошла ошибка при установке Python. (7/${commands})\n${end_process_line}"
      exit 2
    fi
    ;;
  *)
    if ! sudo apt install -y python3.11 python3.11-dev python3.11-gdbm python3.11-venv ; then
      echo -e "${start_process_line}\nПроизошла ошибка при установке Python. (7/${commands})\n${end_process_line}"
      exit 2
    fi
    ;;
esac

clear
echo -e "$start_process_line\nСоздаю пользователя и устанавливаю/обновляю Pip...\n$end_process_line"

if [[ "$reinstall" -eq 0 ]]; then
  if ! sudo useradd -m $username ; then
    echo -e "${start_process_line}\nПроизошла ошибка при создании пользователя. (8/${commands})\n${end_process_line}"
    exit 2
  fi
else
  echo -e "${CYAN}Переустановка: пользователь ${username} уже существует, пропускаю useradd.${RESET}"
fi

venv_exists=0
if [[ -x "/home/$username/pyvenv/bin/python" ]]; then
  venv_exists=1
  echo -e "${CYAN}Виртуальное окружение уже есть, обновляю pip...${RESET}"
fi

if [[ "$venv_exists" -eq 0 ]]; then
case $distro_version in
  "24.04" | "24.10")
    if ! sudo -u $username python3.12 -m venv /home/$username/pyvenv ; then
      echo -e "${start_process_line}\nПроизошла ошибка при создании виртуального окружения. (9/${commands})\n${end_process_line}"
      exit 2
    fi
    ;;
  *)
    if ! sudo -u $username python3.11 -m venv /home/$username/pyvenv ; then
      echo -e "${start_process_line}\nПроизошла ошибка при создании виртуального окружения. (9/${commands})\n${end_process_line}"
      exit 2
    fi
    ;;
esac
fi

if ! sudo /home/$username/pyvenv/bin/python -m ensurepip --upgrade ; then
  echo -e "${start_process_line}\nПроизошла ошибка при установке Pip. (10/${commands})\n${end_process_line}"
  exit 2
fi

if ! sudo -u $username /home/$username/pyvenv/bin/python -m pip install --upgrade pip ; then
  echo -e "${start_process_line}\nПроизошла ошибка при обновлении Pip. (11/${commands})\n${end_process_line}"
  exit 2
fi

if ! sudo chown -hR $username:$username /home/$username/pyvenv ; then
  echo -e "${start_process_line}\nПроизошла ошибка при изменении владельца виртуального окружения. (12/${commands})\n${end_process_line}"
  exit 2
fi

clear
echo -e "$start_process_line\nУстанавливаю PlayerokCardinal...\n$end_process_line"

if ! sudo apt install -y git ; then
  echo -e "${start_process_line}\nПроизошла ошибка при установке Git. (13/${commands})\n${end_process_line}"
  exit 2
fi

gh_repo="KITUSTTT/PlayerokCardinal"
poc_dir="/home/$username/PlayerokCardinal"

sudo git config --global --add safe.directory "$poc_dir" 2>/dev/null || true

if [[ -d "$poc_dir/.git" ]]; then
  echo -e "${CYAN}Репозиторий найден, выполняю git pull...${RESET}"
  if ! sudo -u $username git -C "$poc_dir" pull ; then
    echo -e "${start_process_line}\nПроизошла ошибка при обновлении репозитория. (14/${commands})\n${end_process_line}"
    exit 2
  fi
elif [[ -d "$poc_dir" ]]; then
  echo -e "${RED}Папка $poc_dir существует, но это не git-репозиторий.${RESET}"
  echo -e "${CYAN}Переименуйте или удалите её вручную и запустите установку снова.${RESET}"
  exit 2
else
  if ! sudo -u $username git clone https://github.com/${gh_repo}.git "$poc_dir" ; then
    echo -e "${start_process_line}\nПроизошла ошибка при клонировании репозитория. (14/${commands})\n${end_process_line}"
    exit 2
  fi
fi

if ! sudo -u $username /home/$username/pyvenv/bin/pip install -U -r "$poc_dir/requirements.txt" ; then
  echo -e "${start_process_line}\nПроизошла ошибка при установке необходимых Py-пакетов. (15/${commands})\n${end_process_line}"
  exit 2
fi

clear
echo -e "$start_process_line\nСоздаю ссылку на файл фонового процесса...\n$end_process_line"

if ! sudo ln -sf /home/$username/PlayerokCardinal/PlayerokCardinal@.service /etc/systemd/system/PlayerokCardinal@.service ; then
  echo -e "${start_process_line}\nПроизошла ошибка при создании ссылки на файл фонового процесса. (16/${commands})\n${end_process_line}"
  exit 2
fi

if ! sudo install -m 755 /home/$username/PlayerokCardinal/scripts/pocctl.sh /usr/local/bin/pocctl ; then
  echo -e "${start_process_line}\nПроизошла ошибка при установке pocctl. (16.1/${commands})\n${end_process_line}"
  exit 2
fi

sudo tee /home/$username/POC_SERVICE.txt >/dev/null <<EOF
Playerok Cardinal — управление сервисом
======================================
Systemd unit: PlayerokCardinal@${username}
НЕ используйте: PlayerokCardinalPOC, playerok-cardinal, POC@poc

Команды (от root):
  sudo pocctl start
  sudo pocctl stop
  sudo pocctl restart
  sudo pocctl status
  sudo pocctl logs
  sudo pocctl update
  sudo pocctl health

Или напрямую:
  sudo systemctl restart PlayerokCardinal@${username}
  sudo systemctl status PlayerokCardinal@${username} -n100
EOF
sudo chown $username:$username /home/$username/POC_SERVICE.txt

clear
echo -e "$start_process_line\nНастраиваю кодировку сервера...\n$end_process_line"

case $distro_version in
  "11" | "12")
    if ! sudo apt install -y locales locales-all ; then
      echo -e "${start_process_line}\nПроизошла ошибка при установке локализаций. (17/${commands})\n${end_process_line}"
      exit 2
    fi
    ;;
  *)
    if ! sudo apt install -y language-pack-en ; then
      echo -e "${start_process_line}\nПроизошла ошибка при установке языковых пакетов. (17/${commands})\n${end_process_line}"
      exit 2
    fi
    ;;
esac

clear
echo -e $logo
echo -e '\n\n\e[1;91m * GitHub \e[1;96mgithub.com/KITUSTTT/PlayerokCardinal\e[0m'
echo -e '\e[1;91m * Telegram \e[1;96mt.me/KaDerix\e[0m'

echo -e "\n\n\e[1;92m################################################################################"
echo -e "Установка завершена."
echo -e "Запускаю первичную настройку..."
echo -e "################################################################################\e[0m"
sleep 3
clear

echo -e "\n${CYAN}Начинаю первичную настройку. Пожалуйста, ответь на все вопросы...${RESET}\n"
echo -e "${CYAN}ВНИМАНИЕ: Сейчас будет запущена первичная настройка.${RESET}"
echo -e "${CYAN}Пожалуйста, ответь на все вопросы, которые появятся на экране.${RESET}\n"
sleep 3

# Проверяем, есть ли уже конфиг
if [ ! -f "/home/$username/PlayerokCardinal/configs/_main.cfg" ]; then
    # Запускаем first_setup с правильным перенаправлением stdin (как в FunPayCardinal)
    sudo -u $username LANG=en_US.utf8 /home/$username/pyvenv/bin/python /home/$username/PlayerokCardinal/main.py <&1
    
    # Проверяем, создался ли конфиг
    if [ ! -f "/home/$username/PlayerokCardinal/configs/_main.cfg" ]; then
        echo -e "\n${RED}ОШИБКА: Конфиг не был создан!${RESET}"
        echo -e "${CYAN}Попробуй запустить вручную:${RESET}"
        echo -e "${CYAN}sudo -u $username bash -c 'cd /home/$username/PlayerokCardinal && /home/$username/pyvenv/bin/python main.py'${RESET}"
        exit 1
    fi
    echo -e "\n${GREEN}✓ Первичная настройка завершена!${RESET}\n"
else
    echo -e "\n${CYAN}Конфиг уже существует, пропускаю первичную настройку.${RESET}\n"
    echo -ne "\n${RED}Файл конфигурации найден.${RESET} Хотите добавить Telegram прокси? [y/n]:  "
    read edit_config
    case "$edit_config" in
        [yY]|[yY][eE][sS])
            echo -ne "${CYAN}Запускаем редактирование Telegram прокси...${RESET}\n\n"
            sudo -u $username LANG=en_US.utf8 /home/$username/pyvenv/bin/python -W ignore::SyntaxWarning /home/$username/PlayerokCardinal/setup_telegram_proxy.py <&1
            ;;
        *)
            echo -ne "${CYAN}Редактирование пропущено.${RESET}"
            ;;
    esac
fi

sleep 2

sudo systemctl daemon-reload
sudo systemctl enable PlayerokCardinal@$username.service
sudo systemctl restart PlayerokCardinal@$username.service
sleep 3

if ! systemctl is-active --quiet PlayerokCardinal@$username.service ; then
  echo -e "\n${RED}ОШИБКА: сервис PlayerokCardinal@${username} не запустился!${RESET}"
  echo -e "${CYAN}Последние строки лога:${RESET}"
  journalctl -u PlayerokCardinal@$username.service -n 40 --no-pager
  echo -e "\n${CYAN}Проверка: sudo pocctl health${RESET}"
  exit 1
fi

clear
echo -e $logo
echo -e '\n\n\e[1;91m * GitHub \e[1;96mgithub.com/KITUSTTT/PlayerokCardinal\e[0m'
echo -e '\e[1;91m * Telegram \e[1;96mt.me/KaDerix\e[0m'

echo -e "\n\n\e[1;92m################################################################################"
echo -e "${RED}!СДЕЛАЙ СКРИНШОТ!${CYAN}!СДЕЛАЙ СКРИНШОТ!${RED}!СДЕЛАЙ СКРИНШОТ!${CYAN}!СДЕЛАЙ СКРИНШОТ!"
echo -e "\nГотово!"
echo -e "POC запущен как фоновый процесс!"
echo -e "Теперь напиши своему Telegram-боту."
echo -e "\n\e[1;92mДля управления POC используй \e[93msudo pocctl restart\e[1;92m (рекомендуется)"
echo -e "Сервис systemd: \e[93mPlayerokCardinal@${username}\e[1;92m"
echo -e "Подсказка сохранена в \e[93m/home/${username}/POC_SERVICE.txt\e[1;92m"
echo -e "\n\e[1;92mДля остановки POC: \e[93msudo pocctl stop\e[1;92m"
echo -e "Для запуска POC: \e[93msudo pocctl start\e[1;92m"
echo -e "Для перезапуска POC: \e[93msudo pocctl restart\e[1;92m"
echo -e "Для просмотра логов: \e[93msudo pocctl logs\e[1;92m"
echo -e "Для обновления кода: \e[93msudo pocctl update\e[1;92m"
echo -e "Проверка состояния: \e[93msudo pocctl health\e[1;92m"
echo -e "${RED}* НЕ используй PlayerokCardinalPOC или playerok-cardinal — таких сервисов нет.\e[1;92m"
echo -e "################################################################################\e[0m"

echo -ne "\n\n${CYAN}Сделал скриншот? ${PURPLE_LIGHT}Тогда нажми Enter, чтобы продолжить.${RESET}"
read
clear

