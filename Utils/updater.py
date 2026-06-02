"""
Проверка на обновления.
"""
import time
from logging import getLogger
from locales.localizer import Localizer
import requests
import os
import zipfile
import shutil
import json

logger = getLogger("POC.update_checker")
localizer = Localizer()
_ = localizer.translate

HEADERS = {
    "accept": "application/vnd.github+json"
}

# Пользовательские данные — не удалять при установке релиза (delete.json в архиве).
_PRESERVE_DELETE_PREFIXES = ("storage/",)
_PRESERVE_DELETE_SUFFIXES = ("_config.json", "_settings.json", "_data.json")


def _should_preserve_on_delete(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    if any(normalized.startswith(prefix) for prefix in _PRESERVE_DELETE_PREFIXES):
        return True
    if any(normalized.endswith(suffix) for suffix in _PRESERVE_DELETE_SUFFIXES):
        return True
    return False


def _backup_plugin_configs() -> dict[str, bytes]:
    backups: dict[str, bytes] = {}
    plugins_dir = "plugins"
    if not os.path.isdir(plugins_dir):
        return backups
    for name in os.listdir(plugins_dir):
        if not name.endswith(".json"):
            continue
        path = os.path.join(plugins_dir, name)
        if os.path.isfile(path):
            try:
                with open(path, "rb") as f:
                    backups[path] = f.read()
            except OSError as ex:
                logger.debug("backup plugin config %s: %s", path, ex)
    storage_plugins = os.path.join("storage", "plugins")
    if os.path.isdir(storage_plugins):
        for name in os.listdir(storage_plugins):
            if not name.endswith(".json"):
                continue
            path = os.path.join(storage_plugins, name)
            if os.path.isfile(path):
                try:
                    with open(path, "rb") as f:
                        backups[path] = f.read()
                except OSError as ex:
                    logger.debug("backup plugin config %s: %s", path, ex)
    return backups


def _restore_plugin_configs(backups: dict[str, bytes]) -> None:
    for path, content in backups.items():
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "wb") as f:
                f.write(content)
        except OSError as ex:
            logger.warning("Не удалось восстановить конфиг плагина %s: %s", path, ex)


class Release:
    """
    Класс, описывающий релиз.
    """

    def __init__(self, name: str, description: str, sources_link: str):
        """
        :param name: название релиза.
        :param description: описание релиза (список изменений).
        :param sources_link: ссылка на архив с исходниками.
        """
        self.name = name
        self.description = description
        self.sources_link = sources_link


# Получение данных о новом релизе
def get_tags(current_tag: str) -> list[str] | None:
    """
    Получает все теги с GitHub репозитория.
    :param current_tag: текущий тег.

    :return: список тегов.
    """
    try:
        logger.info(_("upd_checking_tags"))
        page = 1
        json_response: list[dict] = []
        max_pages = 10  # Ограничение на количество страниц
        found_current = False
        
        repo_url = "https://api.github.com/repos/KITUSTTT/PlayerokCardinal/tags"
        logger.info(_("upd_github_repo", repo_url))
        
        while page <= max_pages:
            if page != 1:
                time.sleep(1)
            
            url = f"{repo_url}?page={page}"
            logger.debug(f"Запрос к GitHub API: {url}")
            response = requests.get(url, headers=HEADERS, timeout=10)
            logger.info(f"Статус ответа GitHub API: {response.status_code}")
            
            if not response.status_code == 200:
                logger.warning(_("upd_github_error", response.status_code))
                if page == 1:
                    return None
                break
            page_data = response.json()
            if not page_data:
                logger.info(_("upd_no_more_tags"))
                break
            logger.debug(f"Получено тегов на странице {page}: {len(page_data)}")
            json_response.extend(page_data)
            if any([el.get("name") == current_tag for el in page_data]):
                found_current = True
                logger.info(_("upd_found_current_tag", current_tag))
                break
            page += 1
        
        if not json_response:
            logger.warning(_("upd_no_tags_found"))
            return None
        
        tags = [i.get("name") for i in json_response]
        logger.info(_("upd_tags_found", len(tags)))
        return tags or None
    except Exception as e:
        logger.error(_("upd_exception", str(e)))
        logger.debug("TRACEBACK", exc_info=True)
        return None


def get_next_tag(tags: list[str], current_tag: str):
    """
    Ищет след. тег после переданного.
    Если не находит текущий тег, возвращает первый.
    Если текущий тег - последний, возвращает None.

    :param tags: список тегов.
    :param current_tag: текущий тег.

    :return: след. тег / первый тег / None
    """
    try:
        curr_index = tags.index(current_tag)
    except ValueError:
        return tags[len(tags) - 1]

    if not curr_index:
        return None
    return tags[curr_index - 1]


def get_releases(from_tag: str) -> list[Release] | None:
    """
    Получает данные о доступных релизах, начиная с тега.

    :param from_tag: тег релиза, с которого начинать поиск.

    :return: данные релизов.
    """
    try:
        page = 1
        json_response: list[dict] = []
        max_pages = 10  # Ограничение на количество страниц
        found_tag = False
        
        while page <= max_pages:
            if page != 1:
                time.sleep(1)
            response = requests.get(f"https://api.github.com/repos/KITUSTTT/PlayerokCardinal/releases?page={page}",
                                    headers=HEADERS, timeout=10)
            if not response.status_code == 200:
                logger.debug(f"Update status code is {response.status_code}!")
                if page == 1:
                    return None
                break
            page_data = response.json()
            if not page_data:
                break
            json_response.extend(page_data)
            if any([el.get("tag_name") == from_tag for el in page_data]):
                found_tag = True
                break
            page += 1
        if not json_response:
            logger.warning(_("upd_no_tags_found"))
            return None
        
        logger.debug(f"Всего получено релизов: {len(json_response)}")
        
        result = []
        to_append = False
        found_from_tag = False
        
        for el in json_response[::-1]:
            tag_name = el.get("tag_name")
            logger.debug(f"Проверяю релиз: {tag_name}")
            
            if tag_name == from_tag:
                found_from_tag = True
                to_append = True
                logger.info(_("upd_found_tag", from_tag))
                # Включаем сам тег from_tag в результат
                description = el.get("body", "")
                sources = el.get("zipball_url")
                if "#unskippable" in description:
                    to_append = False
                release = Release(tag_name, description, sources)
                result.append(release)
                if not to_append:
                    break
                continue  # Продолжаем искать релизы после этого тега

            if to_append:
                description = el.get("body", "")
                sources = el.get("zipball_url")
                if "#unskippable" in description:
                    to_append = False
                release = Release(tag_name, description, sources)
                result.append(release)
                if not to_append:
                    break
        
        if result:
            logger.info(_("upd_releases_found", len(result)))
            return result
        
        # Если результат пустой, но тег найден - возможно релиз еще не опубликован
        # Проверяем, есть ли релиз для этого тега
        if found_from_tag:
            for el in json_response:
                if el.get("tag_name") == from_tag:
                    description = el.get("body", "")
                    sources = el.get("zipball_url")
                    release = Release(from_tag, description, sources)
                    result.append(release)
                    logger.info(_("upd_releases_found", len(result)))
                    return result
        
        # Если тег не найден в релизах, но есть в тегах - создаем релиз из тега
        logger.warning(_("upd_no_releases_after_tag", from_tag))
        # Пытаемся получить zipball_url из тега напрямую
        try:
            tag_response = requests.get(f"https://api.github.com/repos/KITUSTTT/PlayerokCardinal/git/refs/tags/{from_tag}",
                                       headers=HEADERS, timeout=10)
            if tag_response.status_code == 200:
                # Тег существует, создаем релиз из тега
                sources = f"https://github.com/KITUSTTT/PlayerokCardinal/archive/refs/tags/{from_tag}.zip"
                release = Release(from_tag, f"Release {from_tag}", sources)
                logger.info(_("upd_releases_found", 1))
                return [release]
        except:
            pass
        
        return None
    except:
        logger.debug("TRACEBACK", exc_info=True)
        return None


def get_new_releases(current_tag) -> int | list[Release]:
    """
    Проверяет на наличие обновлений.

    :param current_tag: тег текущей версии.

    :return: список объектов релизов или код ошибки:
        1 - произошла ошибка при получении списка тегов.
        2 - текущий тег является последним (или релизов нет).
        3 - не удалось получить данные о релизе.
    """
    tags = get_tags(current_tag)
    if tags is None:
        logger.info(_("upd_no_tags_api"))
        return 1

    logger.debug(f"Список тегов: {tags}")
    
    next_tag = get_next_tag(tags, current_tag)
    if next_tag is None:
        logger.info(_("upd_current_is_latest", current_tag))
        return 2

    logger.info(_("upd_next_tag_found", next_tag))
    
    releases = get_releases(next_tag)
    if releases is None:
        logger.warning(_("upd_no_releases_data"))
        return 2  # Если релизов нет, значит текущая версия последняя
    return releases


#  Загрузка нового релиза
def download_zip(url: str) -> int:
    """
    Загружает zip архив с обновлением в файл storage/cache/update.zip.

    :param url: ссылка на zip архив.

    :return: 0, если архив с обновлением загружен, иначе - 1.
    """
    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open("storage/cache/update.zip", 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return 0
    except:
        logger.debug("TRACEBACK", exc_info=True)
        return 1


def extract_update_archive() -> str | int:
    """
    Разархивирует скачанный update.zip.

    :return: название папки с обновлением (storage/cache/update/<папка с обновлением>) или 1, если произошла ошибка.
    """
    try:
        if os.path.exists("storage/cache/update/"):
            shutil.rmtree("storage/cache/update/", ignore_errors=True)
        os.makedirs("storage/cache/update")

        with zipfile.ZipFile("storage/cache/update.zip", "r") as zip:
            folder_name = zip.filelist[0].filename
            zip.extractall("storage/cache/update/")
        return folder_name
    except:
        logger.debug("TRACEBACK", exc_info=True)
        return 1


def zipdir(path, zip_obj):
    """
    Рекурсивно архивирует папку.

    :param path: путь до папки.
    :param zip_obj: объект zip архива.
    """
    for root, dirs, files in os.walk(path):
        if os.path.basename(root) == "__pycache__":
            continue
        for file in files:
            zip_obj.write(os.path.join(root, file),
                          os.path.relpath(os.path.join(root, file),
                                          os.path.join(path, '..')))


def create_backup() -> int:
    """
    Создает резервную копию с папками storage и configs.

    :return: 0, если бэкап создан успешно, иначе - 1.
    """
    try:
        with zipfile.ZipFile("backup.zip", "w") as zip:
            zipdir("storage", zip)
            zipdir("configs", zip)
            zipdir("plugins", zip)
        return 0
    except:
        logger.debug("TRACEBACK", exc_info=True)
        return 1


def extract_backup_archive() -> bool:
    """
    Разархивирует скачанный backup.zip. в storage/cache/backup/

    :return: True, если разархивировано. False в случае ошибок.
    """
    try:
        if os.path.exists("storage/cache/backup/"):
            shutil.rmtree("storage/cache/backup/", ignore_errors=True)
        os.makedirs("storage/cache/backup")

        with zipfile.ZipFile("storage/cache/backup.zip", "r") as zip:
            zip.extractall("storage/cache/backup/")
        return True
    except:
        logger.debug("TRACEBACK", exc_info=True)
        return False


def install_release(folder_name: str) -> int:
    """
    Устанавливает обновление.

    :param folder_name: название папки со скачанным обновлением в storage/cache/update
    :return: 0, если обновление установлено.
        1 - произошла непредвиденная ошибка.
        2 - папка с обновлением отсутствует.
    """
    try:
        release_folder = os.path.join("storage/cache/update", folder_name)
        if not os.path.exists(release_folder):
            return 2

        config_backups = _backup_plugin_configs()

        if os.path.exists(os.path.join(release_folder, "delete.json")):
            with open(os.path.join(release_folder, "delete.json"), "r", encoding="utf-8") as f:
                data = json.loads(f.read())
                for i in data:
                    if _should_preserve_on_delete(i):
                        logger.info("Пропуск удаления пользовательских данных: %s", i)
                        continue
                    if not os.path.exists(i):
                        continue
                    if os.path.isfile(i):
                        os.remove(i)
                    else:
                        shutil.rmtree(i, ignore_errors=True)

        for i in os.listdir(release_folder):
            if i == "delete.json":
                continue

            source = os.path.join(release_folder, i)
            if source.endswith(".exe"):
                if not os.path.exists("update"):
                    os.mkdir("update")
                shutil.copy2(source, os.path.join("update", i))
                continue

            if os.path.isfile(source):
                try:
                    shutil.copy2(source, i)
                except PermissionError:
                    try:
                        if os.path.exists(i):
                            os.chmod(i, 0o777)
                            os.remove(i)
                        shutil.copy2(source, i)
                    except Exception as e:
                        logger.warning(f"Не удалось обновить файл {i}: {e}")
                        continue
            else:
                try:
                    shutil.copytree(source, os.path.join(".", i), dirs_exist_ok=True)
                except PermissionError as e:
                    logger.warning(f"Не удалось обновить директорию {i}: Permission denied. Попробуйте перезапустить бота.")
                    continue

        _restore_plugin_configs(config_backups)
        return 0
    except:
        logger.debug("TRACEBACK", exc_info=True)
        return 1


def install_backup() -> bool:
    """
    Устанавливает бекап.
    """
    try:
        backup_folder = "storage/cache/backup"
        if not os.path.exists(backup_folder):
            return False

        for i in os.listdir(backup_folder):
            source = os.path.join(backup_folder, i)

            if os.path.isfile(source):
                shutil.copy2(source, i)
            else:
                shutil.copytree(source, os.path.join(".", i), dirs_exist_ok=True)
        return True
    except:
        logger.debug("TRACEBACK", exc_info=True)
        return False

