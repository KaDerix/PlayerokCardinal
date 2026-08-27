from colorama import Fore, Back, Style

import logging.handlers

import logging

import re



LOG_COLORS = {

    logging.DEBUG: Fore.BLACK + Style.BRIGHT,

    logging.INFO: Fore.GREEN,

    logging.WARN: Fore.YELLOW,

    logging.ERROR: Fore.RED,

    logging.CRITICAL: Back.RED

}



CLI_LOG_FORMAT = f"{Fore.BLACK + Style.BRIGHT}[%(asctime)s]{Style.RESET_ALL} {Fore.CYAN}│{Style.RESET_ALL} $RESET%(message)s{Style.RESET_ALL}"

CLI_TIME_FORMAT = "%H:%M:%S"

FILE_LOG_FORMAT = "[%(asctime)s][%(filename)s][%(lineno)d]> %(levelname).1s: %(message)s"

FILE_TIME_FORMAT = "%d.%m.%y %H:%M:%S"

CLEAR_RE = re.compile(r"(\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]))|(\n)|(\r)")



def add_colors(text: str) -> str:

    colors = {

        "$YELLOW": Fore.YELLOW,

        "$CYAN": Fore.CYAN,

        "$MAGENTA": Fore.MAGENTA,

        "$BLUE": Fore.BLUE,

        "$GREEN": Fore.GREEN,

        "$BLACK": Fore.BLACK,

        "$WHITE": Fore.WHITE,

        "$B_YELLOW": Back.YELLOW,

        "$B_CYAN": Back.CYAN,

        "$B_MAGENTA": Back.MAGENTA,

        "$B_BLUE": Back.BLUE,

        "$B_GREEN": Back.GREEN,

        "$B_BLACK": Back.BLACK,

        "$B_WHITE": Back.WHITE,

    }

    for c in colors:

        if c in text:

            text = text.replace(c, colors[c])

    return text



class CLILoggerFormatter(logging.Formatter):

    def format(self, record: logging.LogRecord) -> str:

        # Не мутируем record.msg — иначе другие хендлеры получают уже «покрашенный» текст

        msg = add_colors(record.getMessage())

        msg = msg.replace("$RESET", LOG_COLORS[record.levelno])

        log_format = CLI_LOG_FORMAT.replace("$RESET", Style.RESET_ALL + LOG_COLORS[record.levelno])

        return logging.Formatter(log_format, CLI_TIME_FORMAT).format(

            logging.makeLogRecord({**record.__dict__, "msg": msg, "args": ()})

        )



class FileLoggerFormatter(logging.Formatter):

    def format(self, record: logging.LogRecord) -> str:

        msg = CLEAR_RE.sub("", record.getMessage())

        for token in ("$YELLOW", "$CYAN", "$MAGENTA", "$BLUE", "$GREEN", "$BLACK", "$WHITE",

                      "$B_YELLOW", "$B_CYAN", "$B_MAGENTA", "$B_BLUE", "$B_GREEN", "$B_BLACK", "$B_WHITE", "$RESET"):

            msg = msg.replace(token, "")

        return logging.Formatter(FILE_LOG_FORMAT, FILE_TIME_FORMAT).format(

            logging.makeLogRecord({**record.__dict__, "msg": msg, "args": ()})

        )



LOGGER_CONFIG = {

    "version": 1,

    "disable_existing_loggers": False,

    "handlers": {

        "file_handler": {

            "class": "logging.handlers.RotatingFileHandler",

            "level": "INFO",

            "formatter": "file_formatter",

            "filename": "logs/log.log",

            "maxBytes": 20 * 1024 * 1024,

            "backupCount": 25,

            "encoding": "utf-8"

        },

        "cli_handler": {

            "class": "logging.StreamHandler",

            "level": "INFO",

            "formatter": "cli_formatter"

        }

    },

    "formatters": {

        "file_formatter": {

            "()": "Utils.logger.FileLoggerFormatter"

        },

        "cli_formatter": {

            "()": "Utils.logger.CLILoggerFormatter"

        }

    },

    "root": {

        "level": "WARNING",

        "handlers": []

    },

    "loggers": {

        "main": {

            "handlers": ["cli_handler", "file_handler"],

            "level": "INFO",

            "propagate": False

        },

        "PlayerokAPI": {

            "handlers": ["cli_handler", "file_handler"],

            "level": "WARNING",

            "propagate": False

        },

        "playerokapi": {

            "handlers": ["cli_handler", "file_handler"],

            "level": "WARNING",

            "propagate": False

        },

        "POC": {

            "handlers": ["cli_handler", "file_handler"],

            "level": "INFO",

            "propagate": False

        },

        "TGBot": {

            "handlers": ["cli_handler", "file_handler"],

            "level": "INFO",

            "propagate": False

        },

        "TeleBot": {

            "handlers": ["file_handler"],

            "level": "ERROR",

            "propagate": False

        }

    }

}


