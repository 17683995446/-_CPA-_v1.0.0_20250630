"""
日志系统配置模块。

遵循第一性原理：日志是可观测性的基础，应统一配置、分级输出、格式规范。
- 开发环境：控制台彩色输出，DEBUG级别
- 生产环境：结构化JSON格式，INFO级别
- 所有 print() 调用应替换为 logger 调用
"""
import logging
import logging.config
import sys


def setup_logging(level: str = "INFO") -> None:
    """
    初始化全局日志配置。

    使用 dictConfig 模式，支持控制台输出和文件轮转。
    所有模块通过 `logging.getLogger(__name__)` 获取 logger。
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed": {
                "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "standard",
                "stream": sys.stderr,
            },
        },
        "loggers": {
            "app": {
                "level": log_level,
                "handlers": ["console"],
                "propagate": False,
            },
        },
        "root": {
            "level": logging.WARNING,
            "handlers": ["console"],
        },
    }

    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """
    获取统一命名的 logger。

    所有 app 包下的模块自动添加 'app.' 前缀，
    确保日志配置中的 'app' logger 生效。
    """
    if not name.startswith("app."):
        name = f"app.{name}"
    return logging.getLogger(name)
